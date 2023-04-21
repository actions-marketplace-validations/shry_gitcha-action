"""
Class generator
"""
import os
import shutil
import subprocess
import tempfile
from textwrap import dedent
from typing import Literal, Optional

import frontmatter
from github import Github
from langchain.chains.summarize import load_summarize_chain
from langchain.chat_models import ChatOpenAI
from langchain.docstore.document import Document
from langchain.llms import OpenAI
from langchain.prompts.chat import (ChatPromptTemplate,
                                    HumanMessagePromptTemplate,
                                    SystemMessagePromptTemplate)
from langchain.text_splitter import CharacterTextSplitter

from .loader import GitchaDirectoryLoader
from .schemas import ParsedDocs, RepoConfig
from .utils import normalize_path, parse_gitcha_file, user_contact_infos


class LetterOfApplicationError(Exception):
    """Letter of applications already exists"""


class LetterOfApplicationWarning(Exception):
    """Letter of applications warning"""


class LetterOfApplication:
    """
    Creates a letter of application for a specific job 
    based on all your personal files in your git repository

    For a better structure we are using a config file called .gitcha.yaml
    which needs to be present in the root directory.
    """

    repo: RepoConfig
    git_provider: str
    add_prompt: Optional[str] = None
    api: Optional[Github] = None

    docs = ParsedDocs()
    max_token_limit: int

    def __init__(self,
                 git_provider: str,
                 repo: RepoConfig,
                 max_token_limit: int = -1
                 ) -> None:

        if git_provider not in ['github', 'gitlab', 'local']:
            raise LetterOfApplicationError('Wrong git provider')

        if git_provider == 'gitlab':
            raise NotImplementedError('GitLab is currently not supported')

        self.git_provider = git_provider
        self.repo = repo

        if not self.repo.gitcha:
            self.repo.gitcha = parse_gitcha_file(self.repo.path)

        self.max_token_limit = max_token_limit

        # The max_tokens here is por request
        self.llm = OpenAI(temperature=0.2, max_tokens=512)  # type: ignore

    def _get_gitcha_config(self):
        """Get the gitcha dataclass
        """
        if not self.repo.gitcha or not self.repo.gitcha.config:
            raise ValueError('No config provided')

        return self.repo.gitcha.config

    def _init_api(self):
        """Init the API object to GitHub or GitLab
        """

        if not self.repo.api_token or not self.repo.name:
            raise ValueError('No git provider with api token provided')

        if self.git_provider == 'github':
            if not self.api:
                self.api = Github(self.repo.api_token)

            return self.api

        raise ValueError('git provider not supported')

    def _write_file_to_stdout(self, file_path: str):
        """
        Write a file to the output stream 

        For Github its based on: https://docs.github.com/de/actions/using-workflows/workflow-commands-for-github-actions
        """

        if self.git_provider == 'github':

            subprocess.run(';'.join([
                f'GITCHA_APPLICATION=$(cat {file_path})',
                'EOF=$(dd if=/dev/urandom bs=15 count=1 status=none | base64)',
                'echo "application<<$EOF" >> $GITHUB_OUTPUT',
                'echo "$GITCHA_APPLICATION" >> $GITHUB_OUTPUT',
                'echo "$EOF" >> $GITHUB_OUTPUT'
            ]), shell=True, check=False)

        else:
            subprocess.run(';'.join([
                'echo "\n----- Result: -----\n"',
                f'GITCHA_APPLICATION=$(cat {file_path})',
                'echo "$GITCHA_APPLICATION"'
            ]), shell=True, check=False)

    def _summarize_text(self, text: str) -> str:
        """Just summarize a basic string
        """

        if len(text) < 200:
            return text

        text_splitter = CharacterTextSplitter()
        texts = text_splitter.split_text(text)

        docs = [Document(page_content=t) for t in texts]

        self.docs.job_postings = self.docs.job_postings + docs

        chain = load_summarize_chain(
            self.llm, chain_type='map_reduce', verbose=True)
        return chain.run(docs)

    def _get_repo_release(self):
        """
        Get a GitHub release based on the tag name of the workflow release event
        """
        if self.repo.release:
            return self.repo.release

        if not self.repo.ref or not self.repo.ref.startswith('refs/tags/'):
            raise ValueError('Git ref is not provided or not a tag')

        tag_name = self.repo.ref.removeprefix('refs/tags/')

        self.repo.release = self.get_lazy_repo().get_release(id=tag_name)
        return self.repo.release

    def _get_job_source_from_release(self) -> tuple[str, str]:
        """
        Get the job posting from the release
        """

        release = self._get_repo_release()
        job_desc = release.body if release.body else ''

        if job_desc:
            metadata, job_desc = frontmatter.parse(job_desc)
            if metadata.get('prompt'):
                self.add_prompt = metadata.get('prompt')

        return (release.title, job_desc)

    def _get_job_source_from_folder(self) -> list[tuple[str, str, str]]:
        """
        Get the job from a specific folder
        """

        job_posting_path = normalize_path(
            self.repo.path, str(self._get_gitcha_config().job_posting_folder))

        items = job_posting_path.glob('*.md')

        # We just return the first finding
        output = []
        for file in items:
            post = frontmatter.load(file)
            title: Optional[str] = post.get('title')

            # If there is already a created letter we will skip
            if post.get('created'):
                continue

            if not title:
                raise LetterOfApplicationError(
                    f'No title for the job posting under {file}')

            output.append((title, post.content, str(file)))

        if not output:
            raise LetterOfApplicationWarning(
                f'No new job posting file in the {self._get_gitcha_config().job_posting_folder} folder')

        return output

    def _update_folder_file(self, letter: str, file_path: str):
        """
        Update a job posting file based on the file_path
        """

        post = frontmatter.load(file_path)

        post.content = f'{post.content}\n\n---\n\n{letter}'
        post.metadata['created'] = True

        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(frontmatter.dumps(post))

    def _create_release_assets(self, letter_path: str):
        """
        Uploads the assets of the release to currently only github 

        Uploaded assets are:
        * Letter of application
        * Zip of your public folder
        """
        if self.git_provider == 'local':
            return

        release = self._get_repo_release()

        asset = release.upload_asset(
            letter_path, label='Letter of application', content_type='text/markdown')

        # Copy also the public folder as zip
        public_path = normalize_path(
            self.repo.path, str(self._get_gitcha_config().public_folder))
        if os.path.isdir(public_path):
            base_name = os.path.join(self.repo.path, 'documents')
            shutil.make_archive(
                base_name=base_name,
                format='zip',
                root_dir=public_path
            )
            release.upload_asset(
                f'{base_name}.zip', label='Public files as zip', content_type='application/zip')

        # We also create a comment
        self._create_comment(
            message=dedent(f"""
                Successfully created your letter of application.

                You can find all assets under: {release.html_url}
                
                Direct download: {asset.browser_download_url}
            """))

    def _create_comment(self, message: str, sha: Optional[str] = None):
        """
        Create a message as a comment on github/gitlab
        """
        if self.git_provider == 'local':
            return

        repo = self.get_lazy_repo()

        if not sha:
            if not self.repo.ref:
                raise ValueError('Missing git ref')

            sha = self.repo.ref

        repo.get_commit(sha=sha).create_comment(
            body=message
        )

    def check_max_token_limit(self, add: int = 0) -> int:
        """
        Simple prediction and check of the max token limit
        """
        counter = 0
        for doc in self.docs.cv_files + self.docs.job_postings:
            # 512 for the possible max token por completion
            counter += self.llm.get_num_tokens(doc.page_content) + 512

        counter += add

        if self.max_token_limit > 0 and counter > self.max_token_limit:
            raise LetterOfApplicationWarning(
                f'Max token limit reached {counter}/{self.max_token_limit}')

        return counter

    def get_lazy_repo(self):
        """
        Get the repo as a lazy return
        """
        if not self.repo.name:
            raise ValueError('No repo name')

        api = self._init_api()
        return api.get_repo(self.repo.name, lazy=True)

    def summarize_files(self, method: Literal['map_reduce', 'refine'] = 'refine') -> Optional[str]:
        """Create the summarization of all cv files
        """
        if self.docs.cv_summary:
            return self.docs.cv_summary

        loader = GitchaDirectoryLoader(self.repo.path)

        docs = loader.load(gitcha=self.repo.gitcha)

        if not docs:
            raise LetterOfApplicationWarning('No documents to scan')

        self.docs.cv_files = docs

        # check if under max token limit
        self.check_max_token_limit()

        chain = load_summarize_chain(
            self.llm, chain_type=method, verbose=True)
        summary = chain({'input_documents': docs},
                        return_only_outputs=True)

        self.docs.cv_summary = summary.get('output_text', None)
        return self.docs.cv_summary

    def generate_letter_of_application_chat(self, job_title: str, job_desc: str = ''):
        """
        Generate the letter of application
        """
        summary = self.summarize_files()

        if not summary:
            raise ValueError('No summary text')

        if not self.repo.gitcha:
            raise ValueError('No gitcha config')

        chat = ChatOpenAI(temperature=0.6, verbose=True,
                          max_tokens=1000)  # type: ignore

        prompts = []

        prompts.append(SystemMessagePromptTemplate.from_template(
            template='You are a personal job application assistant. The basic personal information of your client are the following: {personal_infos}'
        ))

        human_template = """
        Draft a letter of application for a job with the title '{job_title}'. 
        
        My summarized curriculum vitae is:

        {summary} 

        Use around 150 words:
        """

        if job_desc:
            # We will summarize the job description also
            prompts.append(SystemMessagePromptTemplate.from_template(
                template='The summary of the job description is: \n\n {job_desc}'
            ))
            job_desc = self._summarize_text(job_desc)

        human_message_prompt = HumanMessagePromptTemplate.from_template(
            human_template)
        prompts.append(human_message_prompt)

        if self.repo.gitcha.config:
            prompts.append(SystemMessagePromptTemplate.from_template(
                template=f'You should respond only in {self.repo.gitcha.config.output_lang.upper()}'
            ))

        # prompts.append(HumanMessagePromptTemplate.from_template('How would you improve the prompt?'))

        chat_prompt = ChatPromptTemplate.from_messages(prompts)

        # Generate messages
        messages = chat_prompt.format_prompt(
            personal_infos=user_contact_infos(self.repo.gitcha),
            name=f'{self.repo.gitcha.given_name} {self.repo.gitcha.family_name}',
            job_title=job_title,
            job_desc=job_desc,
            summary=summary
        ).to_messages()

        print(f'Number of analyzed documents: {self.docs.total_files()}')

        prompt_tokens = chat.get_num_tokens_from_messages(messages)
        print(
            f'Token estimation for final prompt: {prompt_tokens}')

        total_limit = self.check_max_token_limit(prompt_tokens+1000)
        print(
            f'Maximum token prediction (prompt/completion): {total_limit} (Only a approximation)')

        # Generate output
        ai_resp = chat(messages=messages)

        if not ai_resp.content:
            raise LetterOfApplicationWarning(
                'AI could not generate a valid output')

        return ai_resp.content

    def create_letter_of_application(self, job_source: str, stdout: bool = True) -> Optional[str]:
        """
        Creates the letter of application in a temp directory as a Markdown file

        Args:
            job_title_from (Literal[&#39;release&#39;, &#39;folder&#39;, &#39;env&#39;]): From where to get the job title
            output (bool, optional): Output result. Defaults to True.
        """

        if job_source not in ['release', 'folder', 'env']:
            raise ValueError('Job source is missing')

        print(f'Create letter of application from a {job_source}')

        if job_source == 'release':
            job_data = [self._get_job_source_from_release(), ]

        elif job_source == 'folder':
            job_data = self._get_job_source_from_folder()

        else:
            job_title, job_desc = os.environ.get(
                'JOB_TITLE', ''), os.environ.get('JOB_DESC', '')
            job_data = [(job_title, job_desc), ]
            if not job_title:
                raise LetterOfApplicationError(
                    'Please provide at least a JOB_TITLE environment variable')

        return_output = None

        # Write the letter to a temp dir
        with tempfile.TemporaryDirectory() as temp_dir:
            new_file_path = os.path.join(temp_dir, 'letter-of-application.md')

            # Only for folder source can be more than one job_data
            for data in job_data:
                # Create the letter
                letter_as_str = self.generate_letter_of_application_chat(
                    data[0], data[1])

                with open(new_file_path, 'a', encoding='utf-8') as temp_file:
                    if temp_file.tell() != 0:
                        temp_file.write('\n\n---\n\n')

                    temp_file.write(f'## Letter for: "{data[0]}"\n\n')

                    temp_file.write(letter_as_str)

                if job_source == 'release':
                    self._create_release_assets(new_file_path)
                elif job_source == 'folder' and len(data) == 3:
                    self._update_folder_file(letter_as_str, data[2])
                    # if last file

            if stdout:
                self._write_file_to_stdout(new_file_path)
            else:
                with open(new_file_path, 'r', encoding='utf-8') as file:
                    return_output = file.read()

        return return_output

    def my_chat(self):
        """_summary_
        """

        chat = ChatOpenAI(temperature=0.6, verbose=True)  # type: ignore

        prompts = []

        prompts.append(SystemMessagePromptTemplate.from_template(
            template='You are a copywriter assistant for a project called gitcha'

        ))

        prompts.append(HumanMessagePromptTemplate.from_template(
            ''
        ))
        chat_prompt = ChatPromptTemplate.from_messages(prompts)

        messages = chat_prompt.format_prompt().to_messages()

        ai_resp = chat(messages=messages)

        return ai_resp.content

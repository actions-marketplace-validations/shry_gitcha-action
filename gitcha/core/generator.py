"""
Class generator
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from textwrap import dedent
from typing import Literal

import frontmatter
from github import Github
from langchain.chains.summarize import load_summarize_chain
from langchain.chat_models import ChatOpenAI
from langchain.docstore.document import Document
from langchain.llms import OpenAI
from langchain.prompts.chat import (ChatPromptTemplate,
                                    HumanMessagePromptTemplate,
                                    SystemMessagePromptTemplate)
from langchain.schema import BaseMessage
from langchain.text_splitter import CharacterTextSplitter

from .loader import GitchaDirectoryLoader
from .schemas import ParsedDocs, RepoConfig
from .utils import normalize_path, parse_gitcha_file, user_contact_infos


class GitchaGeneratorError(Exception):
    """generator error"""


class GitchaGeneratorWarning(Exception):
    """generator warning"""


class GitchaGenerator:
    """
    Generates job specific texts with OpenAI 
    based on all your personal files in your git repository

    For a better structure we are using a config file called .gitcha.yaml
    which needs to be present in the root directory.
    """

    repo: RepoConfig
    git_provider: str

    api: Github | None = None

    docs = ParsedDocs()
    max_token_limit: int

    def __init__(self,
                 git_provider: str,
                 repo: RepoConfig,
                 max_token_limit: int = -1
                 ) -> None:

        if git_provider not in ['github', 'gitlab', 'local']:
            raise GitchaGeneratorError('Wrong git provider')

        if git_provider == 'gitlab':
            raise NotImplementedError('GitLab is currently not supported')

        self.git_provider = git_provider
        self.repo = repo

        if not self.repo.gitcha:
            self.repo.gitcha = parse_gitcha_file(self.repo.path)

        self.max_token_limit = max_token_limit

        # The max_tokens here is por request
        self.llm = OpenAI(temperature=0.2, max_tokens=512)  # type: ignore

        self.chat = ChatOpenAI(temperature=0.6, verbose=True,
                               max_tokens=1000)  # type: ignore

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
                f'GITCHA_ANSWER=$(cat {file_path})',
                'EOF=$(dd if=/dev/urandom bs=15 count=1 status=none | base64)',
                'echo "answer<<$EOF" >> $GITHUB_OUTPUT',
                'echo "$GITCHA_ANSWER" >> $GITHUB_OUTPUT',
                'echo "$EOF" >> $GITHUB_OUTPUT'
            ]), shell=True, check=False)

        else:
            subprocess.run(';'.join([
                'echo "\n----- Result: -----\n"',
                f'GITCHA_ANSWER=$(cat {file_path})',
                'echo "$GITCHA_ANSWER"'
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

    def _get_job_source_from_folder(self) -> list[tuple[str, str, str | None]]:
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
            title: str | None = post.get('title')

            # If there is already a created letter we will skip
            if post.get('created'):
                continue

            if not title:
                raise GitchaGeneratorError(
                    f'No title for the job posting under {file}')

            output.append((title, post.content, str(file)))

        if not output:
            print(
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

    def _create_comment(self, message: str, sha: str | None = None):
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

    def _prepare_prompt(self):
        """
        Prepare the basic chat prompt
        """
        return [SystemMessagePromptTemplate.from_template(
            template='You are a personal job application assistant. The basic personal information of your client are the following:\n{personal_infos}'
        ), ]

    def _execute_chat_prompt(self, messages: list[BaseMessage]) -> str:
        """Execute the prompt messages in the chat 

        Args:
            messages (list[BaseMessage]): The prompt messages

        Returns:
            str: The output from OpenAI
        """

        print(f'Number of analyzed documents: {self.docs.total_files()}')

        prompt_tokens = self.chat.get_num_tokens_from_messages(messages)
        print(
            f'Token estimation for final prompt: {prompt_tokens}')

        total_limit = self.check_max_token_limit(prompt_tokens+1000)
        print(
            f'Maximum token prediction (prompt/completion): {total_limit} (Only a approximation)')

        # Generate output
        ai_resp = self.chat(messages=messages)

        if not ai_resp.content:
            raise GitchaGeneratorWarning(
                'AI could not generate a valid output')

        return ai_resp.content

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
            raise GitchaGeneratorWarning(
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

    def summarize_files(self, method: Literal['map_reduce', 'refine'] = 'refine') -> str | None:
        """Create the summarization of all cv files
        """
        if self.docs.cv_summary:
            return self.docs.cv_summary

        loader = GitchaDirectoryLoader(self.repo.path)

        docs = loader.load(gitcha=self.repo.gitcha)

        if not docs:
            raise GitchaGeneratorWarning('No documents to scan')

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

        prompts = self._prepare_prompt()

        human_template = """
        Draft me a letter of application for a job with the title '{job_title}'. 
        
        My summarized curriculum vitae is:

        {summary} 

        Use around 150 words.
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

        chat_prompt = ChatPromptTemplate.from_messages(prompts)

        # Generate messages
        messages = chat_prompt.format_prompt(
            personal_infos=user_contact_infos(self.repo.gitcha),
            name=f'{self.repo.gitcha.given_name} {self.repo.gitcha.family_name}',
            job_title=job_title,
            job_desc=job_desc,
            summary=summary
        ).to_messages()

        return self._execute_chat_prompt(messages)

    def create_letter_of_application(self, create_release_assets: bool, stdout: bool = True) -> str | None:
        """
        Creates the letter of application in a temp directory as a Markdown file

        Args:
            create_release_assets (bool): Create release assets from the output
            stdout (bool, optional): Output result. Defaults to True.
        """

        print('Create letter of application from the source files')

        job_data = self._get_job_source_from_folder()

        job_title, job_desc = os.environ.get(
            'GITCHA_JOB_TITLE'), os.environ.get('GITCHA_JOB_DESC', '')

        if job_title:
            job_data.append((job_title, job_desc, None))

        if not job_data:
            raise GitchaGeneratorError(
                'Please provide at least a GITCHA_JOB_TITLE environment variable')

        return_output = None

        # Write the letter to a temp dir
        with tempfile.TemporaryDirectory() as temp_dir:
            new_file_path = os.path.join(temp_dir, 'letter-of-application.md')

            # Only in folders can be more than one job_data
            for data in job_data:
                # Create the letter
                letter_as_str = self.generate_letter_of_application_chat(
                    data[0], data[1])

                with open(new_file_path, 'a', encoding='utf-8') as temp_file:
                    if temp_file.tell() != 0:
                        temp_file.write('\n\n---\n\n')

                    temp_file.write(f'## Letter for: "{data[0]}"\n\n')

                    temp_file.write(letter_as_str)

                # if a third value is provided, it is a file path
                if data[2]:
                    self._update_folder_file(letter_as_str, data[2])

            if create_release_assets:
                self._create_release_assets(new_file_path)

            if stdout:
                self._write_file_to_stdout(new_file_path)
            else:
                with open(new_file_path, 'r', encoding='utf-8') as file:
                    return_output = file.read()

        return return_output

    def generate_general_prompt(self, prompt_text: str):
        """
        Ask a specific question based on the summary of your files
        """
        summary = self.summarize_files()

        if not summary:
            raise ValueError('No summary text')

        if not self.repo.gitcha:
            raise ValueError('No gitcha config')

        prompts = self._prepare_prompt()

        human_template = """
        My summarized curriculum vitae is:

        {summary} 

        ---

        {prompt}
        """

        prompts.append(HumanMessagePromptTemplate.from_template(
            human_template))

        if self.repo.gitcha.config:
            prompts.append(SystemMessagePromptTemplate.from_template(
                template=f'You should respond only in {self.repo.gitcha.config.output_lang.upper()}'
            ))

        chat_prompt = ChatPromptTemplate.from_messages(prompts)

        # Generate messages
        messages = chat_prompt.format_prompt(
            personal_infos=user_contact_infos(self.repo.gitcha),
            prompt=prompt_text,
            summary=summary
        ).to_messages()

        return self._execute_chat_prompt(messages)

    def answer(self, prompt_text: str | None = None, stdout: bool = True) -> str | None:
        """
        Execute a general prompt about the repo and return the answer
        """

        print('Get an answer based on the summary of your repo files')

        prompt_text = os.environ.get('GITCHA_PROMPT', prompt_text)

        if not prompt_text:
            raise GitchaGeneratorError(
                'Please provide at least a GITCHA_PROMPT environment variable')

        output = self.generate_general_prompt(prompt_text)

        with tempfile.TemporaryDirectory() as temp_dir:
            new_file_path = os.path.join(temp_dir, 'output.md')
            with open(new_file_path, 'w', encoding='utf-8') as temp_file:
                temp_file.write(output)

            if stdout:
                self._write_file_to_stdout(new_file_path)

        if not stdout:
            return output

        return None

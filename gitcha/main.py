"""
Create my CV
"""
import logging
import os
import pathlib

from dotenv import load_dotenv

from gitcha.core.generator import (GitchaGenerator, GitchaGeneratorError,
                                   GitchaGeneratorWarning, RepoConfig)

load_dotenv()

# Root folder of the entrypoint
ROOT_FOLDER = str(pathlib.Path(__file__).parent.parent.resolve())

# Which git provider (github / gitlab / local)
GIT_PROVIDER = os.environ.get('GIT_PROVIDER', 'local')

# The name of the repository in GitHub or GitLab (namespace/name)
REPO_NAME = os.environ.get(
    'GITHUB_REPOSITORY', os.environ.get('CI_PROJECT_NAME'))

# the api token to connect with the git provider
REPO_API_TOKEN = os.environ.get('GIT_PROVIDER_API_TOKEN')

# Path to the repository folder we want to scan
REPO_PATH = os.environ.get(
    'GIT_FOLDER_PATH', os.environ.get('GITHUB_WORKSPACE', ROOT_FOLDER))

# The fully-formed ref of the branch or tag that triggered the event
GIT_EVENT_REF = os.environ.get(
    'GITHUB_REF', os.environ.get('CI_COMMIT_REF_NAME'))

# the type of action: 'letter-of-application', 'prompt'
GITCHA_ACTION = os.environ.get(
    'GITCHA_ACTION', 'letter-of-application')


# The maximum token limit for the whole generation. This is experimental
# -1 == no limit
MAX_TOKEN_LIMIT = os.environ.get(
    'MAX_TOKEN_LIMIT', -1)


if __name__ == '__main__':

    generator = GitchaGenerator(
        git_provider=GIT_PROVIDER,
        repo=RepoConfig(
            path=REPO_PATH,
            name=REPO_NAME,
            api_token=REPO_API_TOKEN,
            ref=GIT_EVENT_REF
        ),
        max_token_limit=int(MAX_TOKEN_LIMIT)
    )

    try:
        if GITCHA_ACTION == 'letter-of-application':
            generator.create_letter_of_application(
                create_release_assets=(os.environ.get(
                    'GITHUB_EVENT_NAME') == 'release')
            )
        else:
            generator.create_general_prompt()
    except GitchaGeneratorError as exc:
        logging.error(exc)
    except GitchaGeneratorWarning as exc:
        logging.warning(exc)

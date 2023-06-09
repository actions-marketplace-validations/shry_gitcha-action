"""
Conftest
"""
import os
from pathlib import Path
from textwrap import dedent

import pytest
from dotenv import load_dotenv

from gitcha import GitchaGenerator, RepoConfig

ROOT_PATH = Path(__file__).resolve(strict=True).parent.parent


@pytest.fixture(autouse=True)
def setup_envs():
    """
    Setup dotenv
    """
    load_dotenv(dotenv_path=os.path.join(ROOT_PATH, '.env'))


@pytest.fixture(name='gitcha_yaml')
def basic_gitcha_yaml():
    """
    return basic gitcha config
    """
    return dedent(
        """
        family_name: Gates
        given_name: Bill
        home_office: true
        email: test@example.com
        birth_date: 1970-01-01
        knows_about:
          - test sdsd12
          - halloasd asdsdsHALLOd
          - waswwwww
        websites:
          - http://www.google.com
        """
    )


@pytest.fixture(name='tmp_repo_folder')
def repo_tmp(tmp_path, gitcha_yaml):
    """Create a default repo structure
    """
    gitcha = tmp_path / '.gitcha.yaml'
    gitcha.write_text(gitcha_yaml)

    # Add readme
    readme = tmp_path / 'README.md'
    readme.write_text('# My personal vita')

    posting_folder = tmp_path / 'job_postings'
    posting_folder.mkdir()

    posting = posting_folder / 'test.md'
    posting.write_text('---\ntitle: job title\n---\njob desc')

    return tmp_path


@pytest.fixture
def letter_class(tmp_repo_folder):
    """Return a letter of application class
    """

    test_app = GitchaGenerator(
        git_provider='local',
        repo=RepoConfig(
            path=str(tmp_repo_folder),
            name='test/repo'
        )
    )

    return test_app

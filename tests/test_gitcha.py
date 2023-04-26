"""
Some basic tests
We need to write some more
"""
import pytest

from gitcha import GitchaGenerator, RepoConfig
from gitcha.core.generator import GitchaGeneratorError


def test_wrong_provider():
    """Test wrong provider
    """

    with pytest.raises(GitchaGeneratorError) as excinfo:

        GitchaGenerator(
            git_provider='test',
            repo=RepoConfig(
                path='test/path',
                name='test/repo'
            )
        )

    assert 'Wrong git provider' in str(excinfo.value)


def test_job_source_folder(letter_class: GitchaGenerator, tmp_repo_folder, monkeypatch):
    """
    Test job source as folder
    """

    monkeypatch.setattr(GitchaGenerator, 'generate_letter_of_application_chat',
                        lambda *args, **kwargs: 'summary', raising=True)

    letter_class.create_letter_of_application(
        create_release_assets=False, stdout=True)

    with open(tmp_repo_folder / 'job_postings' / 'test.md', encoding='utf-8') as file:
        assert file.read() == '---\ncreated: true\ntitle: job title\n---\n\njob desc\n\n---\n\nsummary'


def test_job_source_folder_return(letter_class: GitchaGenerator, monkeypatch):
    """
    Test return output
    """

    monkeypatch.setattr(GitchaGenerator, 'generate_letter_of_application_chat',
                        lambda *args, **kwargs: 'summary', raising=True)

    summary = letter_class.create_letter_of_application(
        create_release_assets=False, stdout=False)

    assert summary == '## Letter for: "job title"\n\nsummary'

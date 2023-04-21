"""
Some basic tests
We need to write some more
"""
import pytest

from gitcha import LetterOfApplication, RepoConfig
from gitcha.core.generator import LetterOfApplicationError


def test_wrong_provider():
    """Test wrong provider
    """

    with pytest.raises(LetterOfApplicationError) as excinfo:

        LetterOfApplication(
            git_provider='test',
            repo=RepoConfig(
                path='test/path',
                name='test/repo'
            )
        )

    assert 'Wrong git provider' in str(excinfo.value)


def test_job_source_folder(letter_class: LetterOfApplication, tmp_repo_folder, monkeypatch):
    """
    Test job source as folder
    """

    monkeypatch.setattr(LetterOfApplication, 'generate_letter_of_application_chat',
                        lambda *args, **kwargs: 'summary', raising=True)

    letter_class.create_letter_of_application(job_source='folder', stdout=True)

    with open(tmp_repo_folder / 'job_postings' / 'test.md', encoding='utf-8') as file:
        assert file.read() == '---\ncreated: true\ntitle: job title\n---\n\njob desc\n\n---\n\nsummary'


def test_job_source_folder_return(letter_class: LetterOfApplication, monkeypatch):
    """
    Test return output
    """

    monkeypatch.setattr(LetterOfApplication, 'generate_letter_of_application_chat',
                        lambda *args, **kwargs: 'summary', raising=True)

    summary = letter_class.create_letter_of_application(
        job_source='folder', stdout=False)

    assert summary == '## Letter for: "job title"\n\nsummary'

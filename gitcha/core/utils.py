"""
Some small utils we need
"""
import os
from pathlib import Path

import yaml

from .schemas import GitchaYaml


def normalize_path(path: str, folder_path: str) -> Path:
    """
    Just some fix to normalize the gitcha config folder files
    """

    folder_name = f'/{folder_path.lstrip("/.")}'

    # normalize
    folder_name = os.path.normpath(folder_name)
    folder_name = folder_name[1:] if folder_name.startswith(
        '/') else folder_name

    return Path(os.path.join(path, folder_name))


def guess_gitcha_source():
    """
    Guess the source we want to use based on the provided envs

    DEPRECATED
    """
    if os.environ.get('GITHUB_EVENT_NAME') == 'release':
        return 'release'

    if os.environ.get('GITHUB_EVENT_NAME') == 'push':
        return 'folder'

    if os.environ.get('GITHUB_EVENT_NAME') == 'issue':
        return 'issue'

    return 'env'


def parse_gitcha_file(root_path: str):
    """Parse the gitcha file and return
    """
    for file in ['.gitcha.yml', '.gitcha.yaml']:
        yaml_file = os.path.join(root_path, file)

        if not os.path.exists(yaml_file):
            continue

        with open(yaml_file, encoding='utf-8') as file_handler:
            yaml_content = file_handler.read()

            gitcha_config = yaml.safe_load(yaml_content)

        return GitchaYaml.parse_obj(gitcha_config)

    raise ValueError(f'No .gitcha.yml file found under {root_path}')


def user_contact_infos(gitcha: GitchaYaml) -> str:
    """
    Return basic user contact information as string
    """
    output = f'Full name: {gitcha.given_name} {gitcha.family_name}\n\n'

    if gitcha.birth_date:
        output += f'Born: {gitcha.birth_date}\n\n'

    if gitcha.pronouns:
        output += f'Pronouns: {gitcha.pronouns}\n\n'

    if gitcha.knows_language:
        langs = ', '.join(gitcha.knows_language)
        output += f'Speaks languages: {langs}\n\n'

    if gitcha.knows_coding:
        coding = ', '.join(gitcha.knows_coding)
        output += f'Knows following programming languages: {coding}\n\n'

    if gitcha.nationality:
        output += f'Nationality: {gitcha.nationality}\n\n'

    if gitcha.highest_lvl_education:
        output += f'Highest level of education: {gitcha.highest_lvl_education}\n\n'

    if gitcha.phone:
        output += f'Phone number: {gitcha.phone}\n\n'

    if gitcha.email:
        output += f'E-Mail: {gitcha.email}\n\n'

    if gitcha.address:
        output += f'Hometown address: {gitcha.address.street_address} {gitcha.address.city} {gitcha.address.country}'

    return output

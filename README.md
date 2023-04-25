# Gitcha

This Github Action generates a OpenAI generated letter of application based on the entire curriculum vitae files in your repository (PDFs, Docs, Markdown etc.)

## Idea

A lot of developers are using a git repo for managing there CV files, job history, certificates etc. 
Why not combine your CV repo with the power of (Open)AI?

## Usage

To use this action, you need a git repository with at least some files with personal information of you and an OpenAI API key.
For GitHub we recommend you use the `release` workflow:

1. When you have found an interessting job position: Create a new release
2. For the release title you should use the job title and for description the job description
3. Save the release and wait a little bit. You will be notified when the magic has happend

To prevent wrong data injection gitcha only searchs for informations in:

* README.md
* `/public` - [config.public_folder]: All public files you want to distribute along your letter
* `/work_log` - [config.work_history_folder]: Your work history (letter of reference etc.)
* `/certs` - [config.certs_folder]: Certificats you have earned
* `/projects` - [config.projects_folder]: Interessting projects to know 

INFO: Don't forget to add a GitHub action secret for the OpenAI API-Key called: `OPENAI_API_KEY`

## Config

In order to optimize the AI generated letter, we need a config file called `.gitcha.yml` in your root folder. 

```yaml
given_name: Bill # Only required field 
family_name: Gates

# Uncomment if you want to change the default settings
config:
  output_lang: English 
#  public_folder: /public
#  work_history_folder: /work_log
#  certs_folder: /certs
#  projects_folder: /projects
```

### Language

If you want to change the output language of your letter of applications, change the variable  `config.output_lang` in your `.gitcha.yml`.


## Template

The easiest way to start is to use the gitcha template under: 


## Workflow for an existing repo

If you want to add the GitHub action to an existing repo, you have to add new workflow file in `.github/workflows/`:

```yaml
name: Generate Letter of Application

on: 
  release:
    types: [published]

jobs:
  gitcha_job:
    runs-on: ubuntu-latest
    name: Create letter of application
    permissions:
      contents: write
      issues: write
      pull-requests: write
    steps:
      - name: Checkout
        uses: actions/checkout@v3
      - name: Gitcha Action
        uses: ./ # Uses an action in the root directory
        id: gitcha
        with:
          open-ai-key: ${{ secrets.OPENAI_API_KEY }}
          repo-token: ${{ secrets.GITHUB_TOKEN }}

      - name: Your letter of application
        run: echo "${{ steps.gitcha.outputs.application }}"

```

Besides that you **need** to create a `.gitcha.yml` in your root folder.


## Test locally

You can test this project locally.

Just `git clone` this repo and execute in the root folder:

```bash
poetry install

# Place your job postings under /path/to/your/git/folder/job_postings as Markdown files and execute:

OPENAI_API_KEY=*** \
GIT_FOLDER_PATH=/path/to/your/git/folder \
GITCHA_JOB_SOURCE=folder \
poetry run python gitcha/main.py
```

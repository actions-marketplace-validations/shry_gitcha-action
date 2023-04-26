# Gitcha

This Github Action generates OpenAI answers based on the entire curriculum vitae files in your repository (PDFs, Docs, Markdown etc.)

## Idea

A lot of developers are using a git repo for managing there CV files, job history, certificates etc. 
Why not combine your CV repo with the power of (Open)AI?

## Usage

To use this action, you need a git repository with at least some files with personal information of you and an OpenAI API key.

### Example use case

Create automatically a *letter of application* for a job:

1. When you have found an interessting job position: Create a new GitHub release
2. For the release title you should use the job title and for description the job description
3. Save the release and wait a little bit. You will be notified when the magic has happend

[Go to the workflow examples](#workflow-for-an-existing-repo)

## Config

In order to optimize the AI generated letter, we need a config file called `.gitcha.yml` in your root folder. 

```yaml
given_name: Bill # Only required field 
family_name: Gates

# Uncomment if you want to change the default settings
config:
  output_lang: English 
#  public_folder: /public
#  work_history_folder: /work_history
#  certs_folder: /certs
#  projects_folder: /projects
```

To prevent wrong data injection gitcha only searchs for informations in:

* README.md
* `/public` - [config.public_folder]: All public files you want to distribute along your letter
* `/work_history` - [config.work_history_folder]: Your work history (letter of reference etc.)
* `/certs` - [config.certs_folder]: Certificats you have earned
* `/projects` - [config.projects_folder]: Interessting projects to know 

INFO: Don't forget to add a GitHub action secret for the OpenAI API-Key called: `OPENAI_API_KEY`


### Language

If you want to change the output language of your letter of applications, change the variable  `config.output_lang` in your `.gitcha.yml`.


## Template

The easiest way to start is to use the gitcha template under: [TBD]


## Workflow for an existing repo

If you want to add the GitHub action to an existing repo, you have to add new workflow file in `.github/workflows/`.

### Letter of application after new release

```yaml
name: Generate Letter of Application

on: 
  release:
    types: [published]

jobs:
  gitcha-job:
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
          action: letter-of-application 
        env:
          GITCHA_JOB_TITLE: ${{ github.event.release.name }}
          GITCHA_JOB_DESC: ${{ github.event.release.description }}

      - name: Your letter of application
        run: echo "${{ steps.gitcha.outputs.answer }}"

```

### Issue prompts

You could also use gitcha to ask general questions about your CV based on a issue you open:

```yaml
name: Ask me anything

on:
  issues:
    types:
      - labeled

jobs:
  gitcha-job:
    if: github.event.label.name == 'question'
    runs-on: ubuntu-latest
    name: Ask me anything
    permissions:
      contents: read
      issues: write
    steps:
      - name: Checkout
        uses: actions/checkout@v3
      - name: Gitcha Action
        uses: ./ # Uses an action in the root directory
        id: gitcha
        with:
          open-ai-key: ${{ secrets.OPENAI_API_KEY }}
          repo-token: ${{ secrets.GITHUB_TOKEN }}
          action: prompt 
        env:
          GITCHA_PROMPT: ${{ github.event.issue.title }}
          
      - name: Your prompt answer
        run: echo "${{ steps.gitcha.outputs.answer }}"
      - name: Add output as comment
        uses: peter-evans/create-or-update-comment@v3
        with:
          issue-number: ${{ github.event.issue.number }}
          body: ${{ steps.gitcha.outputs.answer }}
```


Besides that you always **need** to create a `.gitcha.yml` in your root folder.

## Test locally

You can test this project locally.

Just `git clone` this repo and execute in the root folder:

```bash
poetry install

# Place your job postings under /path/to/your/git/folder/job_postings as Markdown files and execute:

OPENAI_API_KEY=*** \
GIT_FOLDER_PATH=/path/to/your/git/folder \
GITCHA_PROMPT="a question" \
poetry run python gitcha/main.py
```

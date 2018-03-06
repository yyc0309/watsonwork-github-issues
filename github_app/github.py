import hmac
import hashlib
import json
import requests

from flask import current_app, request, Response, Blueprint
from sendmessage import buildAndSend, sendSimpleMessageWithTitle

# Define blueprint module
github = Blueprint('github', __name__, url_prefix='/github')

# Expose endpoint for Github webhooks
@github.route("/<spaceId>", methods=['POST'])
def githubWebhook(spaceId):
  current_app.logger.info('Processing webhook from github')

  body = request.json

  # If body is valid, build message and send to Watson Work Services
  if body != None:
    buildGithubMessage(spaceId, body)
  else:
    raise Exception('Could not process github webhook')

# Build message and send to Watson Work Services
def buildGithubMessage(spaceId, body):
  # Extract information from Github webhook request
  action = body["action"]
  repo = body['repository']
  issue = body["issue"]

  # Build title and message based on Github webhook information
  title = "%s - Issue %s" % (repo["full_name"], action)
  message = "[#%s - %s](%s)\n" % (issue['number'],
                                  issue['title'], issue["html_url"])

  if action == "opened":
    color = "#3d8b38"
    return buildAndSend(spaceId, message, title, color)
  elif action == "closed":
    color = "#cc0000"
    return buildAndSend(spaceId, message, title, color)
  else:
    current_app.logger.info("Unsupported request: %s" % str(body))
    return None

#----------------------Below are functions for calling github api and returning result to workspace via api call-------------------------
ops = { # <operation>: (<expected num of args>, <needs context>)
  'set': (2, False), 
  'list': (1, True), 
  'context': (0, True) 
} 

# Return [<Title>, <Message>]
def callGithubApi(spaceId, contentLst):
  if len(contentLst) == 0:
    return ['Failed', 'Please provide an operation']

  op = contentLst[0]

  if op not in ops:
    return ['Failed', "Operation [%s] is not supported" % op]

  if len(contentLst[1:]) != ops[op][0]:
    return ['Failed', "Operation %s requires %s more additional arguments" % (op, ops[op][0])]

  if ops[op][1] and (not isContextSet()):
    return ['Failed', "Context is not set yet"]

  title, msg = ["Succeeded", ""] 

  if op == 'set':
    owner = contentLst[1]
    repo = contentLst[2]
    current_app.config['GITHUB_OWNER'] = owner
    current_app.config['GITHUB_REPO'] = repo
    msg = "Github context is set to [owner: %s] [repo: %s]" % (owner, repo)
  elif op == 'context':
    curOwner = current_app.config['GITHUB_OWNER']
    curRepo = current_app.config['GITHUB_REPO']
    msg = "Current context is [owner: %s] [repo: %s]" % (curOwner, curRepo)
  elif op == 'list':
    curOwner = current_app.config['GITHUB_OWNER']
    curRepo = current_app.config['GITHUB_REPO']
    baseUrl = current_app.config['GITHUB_API_URL']
    accessToken = "token %s" % current_app.config['GITHUB_ACCESS_TOKEN']
    milestone = contentLst[1]
    url = '/'.join([baseUrl, 'repos', curOwner, curRepo, 'issues'])
    headers = { 'Authorization': accessToken }
    r = requests.get(url, headers = headers)

    if r.status_code != 200:
      return ['Failed', 'Bad request']

    issues = r.json()
    
    filteredIssues = "\n".join(map(lambda x: "Title: %s, Assignee: %s" % (x['title'], x['assignee']), filter(lambda x: x['milestone']['title'] == milestone, issues)))

    if filteredIssues:
      msg = filteredIssues
    else:
      title = 'Failed'
      msg = 'No issue is tagged with milestone: %s' % milestone
  
  return [title, msg]



def isContextSet():
  return ('GITHUB_OWNER' in current_app.config) and ('GITHUB_REPO' in current_app.config)




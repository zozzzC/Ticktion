#A simple script that syncs notion and ticktick tasks together.

#currently using python3.10
import os
import json 
import threading
import config
from notion_client import Client
from pprint import pprint
from datetime import datetime, timedelta
from ticktick.oauth2 import OAuth2
from ticktick.api import TickTickClient
import time

def main():
    initUserVars()
    getAllTasks()
    initLocalDict()

    
def initUserVars():
    global notion, client
    
    try: 
        notion = Client(auth=os.environ["NOTION_TOKEN"])
    except:
        notion = Client(auth=config.notion_token)
    
    auth_client = OAuth2(client_id=config.client_id, client_secret=config.client_secret, redirect_uri=config.uri)   
    
    client = TickTickClient(config.username, config.password, auth_client)
    
    
def checkIfDaylightSavingsIsTrue() -> bool: 
    daylight_savings_in_effect = time.localtime().tm_isdst 
    return daylight_savings_in_effect

#gets all tasks in ticktick initially, syncing to notion 
def initSyncTT():
    #get all list names and their ids, then determine if notion has this or not (mostly if youre using lists)
    all_lists = client.state['projects']
    for key in all_lists:
        thistask = client.task.get_from_project(key.get("id"))
        #for each task, add the task's id as the key, and then the values must be added to a list as the values of the key
        category = key.get("name")
        
        for item in thistask:
            print(item["id"])
            print(item.get("title"))
            
            title = item.get("title")
            
            #TODO: change default priority name to null by default.
            priorityName = "Low" 
            
            if item.get("priority") == 1:
                priorityName = "Low"
            elif item.get("priority") == 3:
               priorityName = "Medium"
            elif item.get("priority") == 5:
                priorityName = "High" 
            
            #TODO: check if task is on repeat and add this when we sync? 
            
            #notionProps contains the dictionary of all notion properties that will be synced to notion from ticktick
            notionProps = {
                'Name' : {'title' : [{'text' : {'content' : title}}]},
                'Priority' : {'select' : {'name' : priorityName}},
                'ticktickID' : {'rich_text' : [{'text' : {'content':item["id"]}}]},
                'Calendar' : {'select' : {'name' : category}},
            }

            if item.get("startDate") is not None: 
                notionProps['Date'] = {}
                notionProps['Date']['date'] = {}
                dateTimeReformat = datetime.strptime(item.get('startDate'), "%Y-%m-%dT%H:%M:%S.%f%z")
                notionProps['Date']['date']['start'] = str(dateTimeReformat) 
                if item.get("isAllDay") == True: 
                    startDate = item.get("startDate")
                    datetimeStart = datetime.strptime(startDate, "%Y-%m-%dT%H:%M:%S.%f%z")
                    datetimeStart = datetimeStart + timedelta(days=1)
                    datetimeStart = datetimeStart.strftime("%Y-%m-%d")
                    notionProps['Date']['date']['start'] = datetimeStart
                    print("Task " + item["id"] + " " + item.get("title") + " is all day, setting start date to " + str(datetimeStart))
                elif item.get("dueDate") is not None: 
                    dateTimeReformat = datetime.strptime(item.get('dueDate'), "%Y-%m-%dT%H:%M:%S.%f%z")
                    notionProps['Date']['date']['end'] = str(dateTimeReformat) 
            
            TTtasks[item['id']] = item
            notion.pages.create(parent={'database_id' : config.db_id}, properties=notionProps, children=[],)
        

#gets all tasks in notion initally, syncing to ticktick
def initSyncNotion():
    #this gets each page in the database specified
    for key in my_page["results"]:
        print(key)
        notionPageID = key["id"]
        titleDict = key['properties']['Name']['title']
        
        if len(titleDict) != 0:
            title = titleDict[0]["text"]["content"]
        elif title is None: 
           title = "" 
        ttID = key['properties']["ticktickID"]["rich_text"]
        
        print(ttID)
        
        calendarDict = key['properties']["Calendar"]['select']

        priorityDetail = key['properties']["Priority"]["select"]
        priorityName = None 
        
        try:
            priorityName = priorityDetail["name"]
        except: 
            priorityName = None
        
        dateDict = key['properties']["Date"]['date']
        dateStart = None
        dateEnd = None
        
        #ticktick uses numbers for its priority API        
        priorityNum = 0
        
        if priorityName is None:
            priorityNum = 0
        elif priorityName == "Low":
            priorityNum = 1
        elif priorityName == "Medium":
            priorityNum = 3
        elif priorityName == "High":
            priorityNum = 5
        
        #TODO: add tags support? but have to add this feature to sdk first

        allday = False
        if dateDict is not None:
            dateStart = dateDict['start']
            #check for daylight savings
            
             
            try:
                dateStart = datetime.strptime(dateStart, "%Y-%m-%dT%H:%M:%S.%f%z") #wont work if theres only a day not a time included
                if time.localtime().tm_isdst == 0: 
                    dateStart = dateStart + timedelta(hours=1)
            except:
                dateStart = datetime.fromisoformat(dateStart)
                if time.localtime().tm_isdst == 0: 
                    dateStart = dateStart + timedelta(hours=1)
                allday = True
                print(str(dateStart))
            try:
                dateEnd = dateDict['end']
                dateEnd = datetime.fromisoformat(dateEnd)
                if time.localtime().tm_isdst == 0: 
                    dateEnd = dateStart + timedelta(hours=1)
                #TODO: if the start and end dates are different, check if it is an all day event, and then dont include time in ticktick
            except:
                dateEnd = None
            
        try:
            calName = calendarDict["name"]
        except:
            print("Calendar name not found, setting calendar to Inbox...")
            calName = 'Inbox'

        #if ttIDTItle is empty, it means the task was just created in notion but not yet added to TickTick. 
        
        if len(ttID) == 0:
            print("ttID length = 0")
        
        
        #if task is ticked off, then don't bother syncing it
        taskDone = False 
        if (key['properties']['Done']['checkbox'] == "False"):
            taskDone = True
        
        print("task done? " + str(taskDone))
                
        if len(ttID) != 0:
            NTTasks[str(ttID[0]['text']['content'])] = key #if ttID exists, then do not create a new task.
            
        print(str(NTTasks))
        
        
        if len(ttID) == 0 & taskDone == False:
            #create new TickTick object, parsing details into it. 
            newTask = client.task.builder(title)
            newTask['startDate'] = None
            newTask['priority'] = priorityNum
            if dateStart is not None:
                newTask['startDate'] = dateStart.strftime("%Y-%m-%dT%H:%M:%S+1300")
            if dateEnd is not None: 
                newTask['dueDate'] = dateEnd.strftime("%Y-%m-%dT%H:%M:%S+1300")
            
            newTask['isAllDay'] = allday 
            #TODO: Add tags ability
            
            
            try:
                projectID = client.get_by_fields(name=calName, search='projects') 
                newTask['projectId'] = projectID['id'] 
            except: #if ID was not found, create new one
                print("ID for project " + calName + " was not found.")
                #TODO: default project creation

            if dateEnd is None: 
                newTask['isAllDay'] = True
            
            
            newTask = client.task.create(newTask)
            
            print("ticktick task: " + str(newTask))
            
            ttIDTitle = newTask['id']


            NTTasks[ttIDTitle] = key
            print("NTTasks: " + str(NTTasks))
            TTtasks[ttIDTitle] = newTask
            ttIDProp = {
                'ticktickID' : {
                    'type' : 'rich_text',
                    'rich_text' : [{
                        'type' : 'text',
                         'text' : {
                             'content' : ttIDTitle
                         }
                    }
                    ]
                }
            }
            
            notion.pages.update(page_id=notionPageID, properties=ttIDProp, children=[])
        
        else: 
            ttID = key
            

def getAllTasks(): #gets all tasks in both ticktick and notion and lists them out
    global TTtasks, NTTasks, my_page
    TTtasks = {}
    NTTasks = {}

    
    my_page = notion.databases.query(
        **{
            "database_id":  "51ef787971fd4dcfadc9827ffa061ce0",
        }
    )
    
    #initSyncTT()
    initSyncNotion()


#initializes cached dictionaries
def initLocalDict():
    dictFilePath = os.getcwd() + '/notiondbs.json'
    global oldNotionDbs, oldTicktickDbs
    oldNotionDbs = {}
    oldTicktickDbs = {}
    
    if (os.path.exists(dictFilePath) == True):
        #TODO: parse the old saved dict. into the python dict
        #pls recheck!
        # Opening JSON file and load into locals
        with open('notiondbs.json') as json_file:
            oldNotionDbs = json.load(json_file)

        print("init local dict notion dbs: " + str(oldNotionDbs))
        
        dictFilePath = os.getcwd() + '/ticktickdbs.json'
    
        with open('ticktickdbs.json') as json_file:
            oldTicktickDbs = json.load(json_file)
        print("init local dict ticktick dbs: " + str(oldTicktickDbs))
 
        checkForChanges()
        #checkForTTCompleted()
        #checkForTTDeleted()
        
    else: 
        #otherwise we are initializing the dict we just found
        file = "notiondbs.json"
        json.dump(NTTasks, open(file, 'w'), indent=4)
        file = "ticktickdbs.json"
        json.dump(TTtasks, open(file, "w"), indent=4)
        
       
    #check matching entries -- if match, save into new, checking differences between the two and update accordingly. 
    


#now, check the local files to see if there is a key 
#if there is a key, then i should update
#if there is not, then i should add 
#if i can't find the equivalent key, then the event must have been deleted or completed. 


#if we need to check which app (tt or notion) to update to, then first compare their details to their previous dictionary (old notion and old ticktick)
#the one whose dict details didnt match means this is the new one, and we must update from there
def checkForChanges():
    global toUpdateNTTasks, toUpdateTTasks
    toUpdateNTTasks = {}
    toUpdateTTasks = {} 
    
    #TODO: check for deleted ticktick tasks first before checking for updates, or else you will get a key error if the task cannot be found in TT. 
    
    print("Checking for changes between current Notion tasks and cached Notion tasks...")
         
    for id, info in NTTasks.items():
        try:
            if oldNotionDbs[id] != NTTasks[id]:
                #hence add into updating tasks list
                #this is notion to ticktick
                print("Found task " + id + " and adding to update dictionary...")
                toUpdateNTTasks[id] = info 
        except: 
            #TODO: if this doesn't work, that means that there was a key error, aka a new task was just added to NTTasks and does not exist in the old tasks yet
            print("Task " + id + " has just been added and cannot be updated. Continuing to find tasks....")
            
    print("Checking for changes between current Ticktick tasks and cached Ticktick tasks...")
    for id, info in TTtasks.items():
            #ticktick to notion update
        try:
            if oldTicktickDbs[id] != TTtasks[info]:
                print("Found task " + id + " and adding to update dictionary...")
                toUpdateTTasks[id] = info
        except:
            print("Task " + id + " has just been added and cannot be updated. Continuing to find tasks....")
    
    #now update all ticktick tasks to notion, all notion tasks to ticktick 
    
    #to update to ticktick, just get the id, search by the id, and then update params accordingly
    #possible params:
    #name, project, tags, status, priority
    checkForChangesTTNotion()
    # checkForChangesNotionTT()
   
   
def checkForChangesTTNotion():
    #update ticktick tasks to notion 
    for id, info in toUpdateTTasks.items(): 
        print(info["id"])
        notionTask = client.task.get_from_project(info["id"]) 
        print(str(notionTask))
        
        
        
        
        
def checkForChangesNotionTT():
    #update notion tasks to ticktick
    for id, info in toUpdateNTTasks.items():
        tickTickTask = client.get_by_id(id)
                
        #update task dictionary with new params

        tickTickTask['title'] = info['properties']['Name']['title'][0]['text']['content']
        
        #TODO: priority should be turned back to 0, 1, 2, 3 
        
        priorityNum = 0
        priorityName = info['properties']['Priority']['select']
        if (priorityName is None):
           priorityNum = 0
        elif priorityName == "Low":
            priorityNum = 1
        elif priorityName == "Medium":
            priorityNum = 3
        elif priorityName == "High":
            priorityNum = 5
       
        
        tickTickTask['priority'] = priorityNum
        
        #check for all day task 
        
        dateDict = info['properties']['Date']['date']
        
        allday = False
        if dateDict is not None:
            dateStart = dateDict['start']
            
            try:
                dateStart = datetime.strptime(dateStart, "%Y-%m-%dT%H:%M:%S.%f%z") #wont work if theres only a day not a time included
            except:
                dateStart = datetime.fromisoformat(dateStart)
                allday = True
                print(str(dateStart))
            try:
                dateEnd = dateDict['end']
                dateEnd = datetime.fromisoformat(dateEnd)
            except:
                dateEnd = None
        
        #check status based on the state in notion
        taskStatusBool = info['properties']['Done']['checkbox'] 
        #depending on the state of checked or unchecked, the ticktick task is either finished or not
        if taskStatusBool == True:
            tickTickTask['status'] = 1
       
        #update calendar names
        if (info['properties']['Calendar']['select'] is None):
            #then field should be 'Inbox'
            calName = "Inbox"
        else: 
            calName = info['properties']['Calendar']['select']['name']
            print(calName)

        
        try:
            projectID = client.get_by_fields(name=str(calName), search='projects') 
            tickTickTask['projectId'] = projectID['id'] 
        except: #if ID was not found, create new one
            print("ID for project " + str(calName) + " was not found. Creating new project...")
        
        print("ticktick task: " + str(tickTickTask))
        
        
        #once completed, sync the newly updated file to ticktick 
        
        updatedTTTask = client.task.update(tickTickTask)
        
        
        
        
        #once all tasks have been update synced, then we store the current sync into our 'cache'.
        #syncBackToCache()

        
        
        
def syncBackToCache():
    file = "notiondbs.json"
    json.dump(NTTasks, open(file, 'w'), indent=4)
    file = "ticktickdbs.json"
    json.dump(TTtasks, open(file, "w"), indent=4) 
    
        
        


#then check if there is a notion id associated with the ticktick event 


#use the ID in ticktick to link it to notion w/ python
#continuously poll notion and ticktick servers, checking if either changed (range 1 year only), and tasks which have not repeated yet. 
#idea: daemon thread? 


#TODO: Checks for the last 100 deleted tasks in Ticktick

    
    
    
    

#TODO: Checks for the last 100 completed tasks in ticktick
def checkForTTCompleted():
    print("Updating task status (Ticktick --> Notion)...") 
    getFromDate = datetime.now() 
    #Check ticktick's most recent 100 completed items. Determine key value, then lookup this key in the cached TT db, if exists, add task to 'completedTTTask' dict
    complete_tasks = client.task.get_completed(datetime.now())
    

    

if __name__ == '__main__':
    main()


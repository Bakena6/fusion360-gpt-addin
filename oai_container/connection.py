
import configparser
import os
from multiprocessing.connection import Listener
from array import array
import traceback
import math
import os
import json
import subprocess
import sys
import time
from openai import OpenAI

user_config = configparser.ConfigParser()
# path to config file containing open ai API keys, Python env path
parent_dir = os.path.dirname(os.getcwd())
config_path = os.path.join(parent_dir,"gpt_config.env")
user_config.read(config_path)
default_config = user_config["DEFAULT"]

#PYTHON_ENV_PATH = default_config["PYTHON_ENV_PATH"]
OPENAI_API_KEY = default_config["OPEN_AI_API_KEY"]

os.environ['OPENAI_API_KEY'] =  OPENAI_API_KEY

ASSISTANT_ID = default_config["ASSISTANT_ID"]

#client = OpenAI(api_key=OPEN_AI_API_KEY)
client = OpenAI()



class Assistant:
    """
    get assistant and create new thread
    base assistant class
    """

    def __init__(self, assistant_id=None, initial_message=None):
        """get assistant and create new thread"""

        self.client = OpenAI()

        # assistant_id is defined in the OpenAI Assistant API website
        self.assistant_id = assistant_id
        print(f'assistant_id: {assistant_id}')


        # TODO eventualy, user should be able to restart thred from Fusion
        # start assistant thread (conversation)
        self.start_thread()

        # run local process server, how Fusion connects
        self.start_server()



    def format_str(self, string, n_char):
        string = str(string)

        spacer_len = max(n_char - len(string), 0)

        spacer = " " *spacer_len 

        return f"{string}{spacer}"





    def start_server(self):

        # run on local host, Fusion client must connect to this address
        address = ('localhost', 6000) # family is deduced to be 'AF_INET'

        with Listener(address, authkey=b'fusion260') as listener:
            with listener.accept() as conn:
                print('CONNECTION ACCEPTED FROM', listener.last_accepted)

                i = 0
                while True:
                    print(f"\n")
                    print(f"{i} WAITING...")

                    # wait for message from user
                    message_text = conn.recv()
                    print(f" MESSAGE RECIEVED: {message_text}")

                    # add message to thread
                    self.add_message(message_text)

                    # once message(s) are added, run
                    self.create_run()

                    # waiting for run
                    self.run = self.get_run_status()

                    run_messages = self.get_messages()

                    # calls in current thread
                    n_calls = 0
                    while self.run.status != "completed":
                        print(f"  N CALL: {n_calls}")
                        self.run = self.get_run_status()
                        #print(f"  RUN STATUS: {self.run.status}")

                        run_messages = self.get_messages()
                        run_steps = self.get_run_steps()

                        if self.run.status == "requires_action":
                            print(f"  TYPE: {self.run.required_action.type}, N STEPS: { len(run_steps.data) } ")

                            for step in run_steps.data:

                                print(f"   N TOOL CALLS: { len(step.step_details.tool_calls) }")
                                if step.status == "completed":
                                    continue

                                print(f"   STEP STATUS: {step.status}")
                                #print(step)

                                #print(step.status)
                                for tool_call in step.step_details.tool_calls:
                                    #tool_call_status

                                    function_name = tool_call.function.name
                                    function_args = tool_call.function.arguments
                                    print(f"    CALL TOOL: {function_name}, {function_args}")
                                    fusion_call = {
                                        "run_status": self.run.status,
                                        "response_type": "tool_call",
                                        "function_name": function_name,
                                        "function_args": function_args
                                    }
                                    conn.send(json.dumps(fusion_call))

                                    # Fusion360 function results
                                    function_results = conn.recv()

                                    tool_outputs = [{
                                        "tool_call_id" : tool_call.id,
                                        "output": function_results
                                    }]

                                    print(f"    FUNC RESULTS: {tool_outputs}")

                                    self.submit_tool_call(tool_outputs)
                                    self.get_run_status()


                        n_calls += 1



                    if self.run.status == "completed":
                        fusion_call = {
                            "run_status": self.run.status,
                            "response_type": "message",
                            "text": message_text
                        }
                        conn.send(json.dumps(fusion_call))

                    #function_results = conn.recv()
                    #print(f"  function results: {function_results}")
                    #print(f"  done")

                    i +=1
                    if i > 50:
                        break


    def start_thread(self):
        """
        start thread (conversation) with Assistant API
        """
        # create new thread
        self.thread = self.client.beta.threads.create()

        self.thread_id = self.thread.id

        ## laste run step
        self.run_steps = None
        print(f'THREAD CREATED: {self.thread.id}')


    def add_message(self, message_text: str):
        """
        create new message and add it to thread
        """
        message = self.client.beta.threads.messages.create(
            thread_id=self.thread_id,
            role="user",
            content=message_text
        )

        self.message_id = message.id
        print(f'  MESSAGE ADDED: {message.id}')


    def create_run(self):
        """create initial run"""

        self.run = self.client.beta.threads.runs.create(
            thread_id=self.thread_id,
            assistant_id=self.assistant_id
        )

        self.run_id = self.run.id
        print(f"  CREATE RUN: status: {self.run.status}")


    def get_run_status(self):
        """
        Poll for run status
        after a run update, status should move to 'queued'
        then then 'in_progress', breakes when status changes
        from 'in_progress'
        """

        #time.sleep(.5)
        # poll the run status
        for i in range(25):

            # poll run status
            run = self.client.beta.threads.runs.retrieve(
                thread_id=self.thread_id,
                run_id=self.run_id,
            )

            print(f"  RUN STATUS {i}: {run.status}")

            # wait for status change event
            if run.status not in ['queued', 'in_progress']:
                break

            time.sleep(1)

        self.run = run
        return run


    def run_status(self):
        """get run status"""
        # get run status
        run = self.client.beta.threads.runs.retrieve(
            thread_id=self.thread_id,
            run_id=self.run_id,
        )

        #self.format_str("", 9)
        #print(f"  RUN STATUS: status: {run.status}")
        return run



    def get_run_steps(self):
        """check if run is complete and get message"""

        run_steps = self.client.beta.threads.runs.steps.list(
            thread_id=self.thread_id,
            run_id=self.run_id,
            order="asc",
            limit=20
        )

        self.run_steps = run_steps

        #for step in run_steps.data[::-1]:
        for step in run_steps.data:

            info = ""
            if step.type == "tool_calls":
                info = step.step_details.tool_calls[0].function.name

            print(f"   STEP: {step.id}, {step.type}, {step.status}, {info} {step.id}")


        return run_steps


    def get_messages(self):
        '''get messages from thread'''

        messages = self.client.beta.threads.messages.list(
            thread_id=self.thread_id,
            # query on the most recent message
            order="asc",
            limit=10
        )

        #message_text = run_messages.data[0].content[0].text.value
        for message in messages.data:
            msg_text = message.content[0].text.value
            msg_role = message.role

            print(f"   MSG: {msg_role}: {msg_text}")

        return messages
    def submit_tool_call(self, response_list: list):
        """
        send tool call responses
        response_list : list of dicts, each dict containg tool_call id and output
        """

        # function reply
        self.run = self.client.beta.threads.runs.submit_tool_outputs(
            thread_id=self.thread_id,
            run_id=self.run_id,
            tool_outputs=response_list
        )

        print(f'  TOOL CALL SUBMITTED: status: {self.run.status}')


    def parse_run_steps(self):
        run_steps = self.run_steps
        client = self.client

        print('-----------')
        for index, step in enumerate(run_steps):
            print(f'{index}: STEP STATUS: {step.status}, STEP TYPE: {step.type}')

            if step.type == 'tool_calls':
                tool_calls = step.step_details.tool_calls
                for call_index, call in enumerate(tool_calls):
                    print(f'  TOOL CALL {call_index}: {call}')

            if step.type == 'message_creation':
                print(f'{step.step_details.message_creation}')

            print(' ')


        run_step = run_steps.data[0]

        thread_id = run_step.thread_id
        step_status = run_step.status
        step_type = run_step.type
        step_details = run_step.step_details

        print(f'STEP STATUS  : {step_status}, STEP TYPE    : {step_type}')
        #print(f'STEP DETAILS : {step_details}')

        if step_type == 'tool_calls':
            tool_calls = run_step.step_details.tool_calls
            self.tool_calls = tool_calls
            #print(f'TOOL_CALLS : {tool_calls}')
            return {'resp_type': 'tool_calls', 'value': tool_calls}

        elif step_type == 'message_creation':
            message_id = run_step.step_details.message_creation.message_id
            #print(f'MESSAGE_ID : {message_id}')
            message = client.beta.threads.messages.retrieve( message_id=message_id, thread_id=thread_id)
            message_text = ''
            for msg in message.content:
                message_text += msg.text.value
            self.message_text = message_text

            return {'resp_type': 'message', 'value': message_text}




    def execute_message(self, message):
        self.create_message(message)
        self.create_run()
        return None


    def execute_steps(self):
        self.get_run_steps()

        steps_resp = self.parse_run_steps()

        return steps_resp


    def send_func_response(self, response_list: list):
        """
        send tool call responses
        response_list : list of dicts, each dict containg tool_call id and output
        """

        # function reply
        run = self.client.beta.threads.runs.submit_tool_outputs(
            thread_id=self.thread_id,
            run_id=self.run_id,
            tool_outputs=response_list
        )

        print(f'RESP RUN STATUS: run_id: {run.id}, status: {run.status}')


    def get_steps(self):
        '''print most recent run steps'''
        print(self.get_run_steps().model_dump_json(indent=4))


    def cancel_run(self):
        run = self.client.beta.threads.runs.cancel(
          thread_id=self.thread_id,
          run_id=self.run_id
        )
        print('RUN CANCEL')




#def get_gpt(initial_message):
#
#    # hardcode assitant id, resuces api calls for now
#    assistant_id = config.ASSASTANT_ID
#
#    gpt = Assistant(assistant_id, initial_message)
#
#    return gpt


if __name__ == "__main__":

    assistant = Assistant(assistant_id =ASSISTANT_ID)








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
import adsk


user_config = configparser.ConfigParser()
# path to config file containing open ai API keys, Python env path
parent_dir = os.path.dirname(os.getcwd())
config_path = os.path.join(parent_dir,"config.env")
user_config.read(config_path)

default_config = user_config["DEFAULT"]
OPENAI_API_KEY = default_config["OPEN_AI_API_KEY"]
os.environ['OPENAI_API_KEY'] =  OPENAI_API_KEY

#client = OpenAI(api_key=OPENAI_API_KEY)
ASSISTANT_ID = default_config["ASSISTANT_ID"]

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
        #self.start_server()

    def format_str(self, string, n_char):
        """uniform print spacing """
        string = str(string)
        spacer_len = max(n_char - len(string), 0)
        spacer = " " *spacer_len 
        return f"{string}{spacer}"


    def update_tools(self, tools):
        """
        update assistant tools, and initial prompt instructions
        """

        # base assistant prompt
        with open("system_instructions.txt") as f:
            instructions = f.read()

        # functions
        tools = json.loads(tools)
        updated_tools = []
        for tool in tools:
            updated_tools.append({"type": "function", "function": tool})

        updated_assistant = client.beta.assistants.update(
            self.assistant_id,
            tools=updated_tools,
            instructions=instructions,
        )

        print(updated_assistant)


    def start_thread(self):
        """
        start thread (conversation) with Assistant API
        """
        # create new thread
        self.thread = self.client.beta.threads.create()

        self.thread_id = self.thread.id

        ## laste run step
        self.run_steps = None
        print(f'Thread created: {self.thread.id}')

    def start_server(self):
        # run on local host, Fusion client must connect to this address
        address = ('localhost', 6000) # family is deduced to be 'AF_INET'

        with Listener(address, authkey=b'fusion260') as listener:

            with listener.accept() as conn:
                print('CONNECTION ACCEPTED FROM', listener.last_accepted)

                i = 0
                while True:
                    print(f"{i} Waiting for user command...")

                    # wait for message from user
                    message_raw = conn.recv()

                    message = json.loads(message_raw)

                    message_type = message["message_type"]

                    #print(f" MESSAGE RECIEVED: {message['content'] }")
                    print(f" MESSAGE RECIEVED")


                    if message_type == "thread_update":
                        message_text = message["content"]

                    # update Assistant meta data
                    elif message_type == "tool_update":
                        tools = message["content"]
                        self.update_tools(tools)
                        continue

                    # update Assistant meta data
                    #elif message_type == "reconnect":
                    #    tools = message["content"]
                    #    self.update_tools(tools)
                    #    continue

                    # add message to thread
                    self.add_message(message_text)

                    # once message(s) are added, run
                    self.stream = self.create_run()

                    event_type = ""
                    message_text = ""

                    while event_type != "thread.run.completed":
                        print(f"THREAD START")

                        for event in self.stream:
                            event_type = event.event
                            data = event.data
                            print(event_type)

                            if event_type == "thread.run.created":

                                # set run id for tool call result calls
                                self.run = event.data
                                self.run_id = event.data.id
                                #print(data)

                                content = {
                                    "run_id": self.run_id,
                                };

                                fusion_call = {
                                    "run_status": "in_progress",
                                    "event": event_type,
                                    "content": content
                                }
                                conn.send(json.dumps(fusion_call))


                            elif event_type == "thread.message.created":
                                print(event)

                                content = {
                                    "message_id": data.id,
                                    "run_id": data.run_id,
                                    "event": event_type,
                                };

                                fusion_call = {
                                    "run_status": "in_progress",
                                    "event": event_type,
                                    "content": content
                                }

                                conn.send(json.dumps(fusion_call))

                            elif event_type == "thread.run.step.created":
                                step_type = data.type

                                print(f"step_type: {step_type}")

                                step_details = data.step_details

                                content = {
                                    "step_id": data.id,
                                    "run_id": data.run_id,
                                    "status": data.status,
                                    "step_type": step_type,
                                    "event": event_type,
                                };
                                fusion_call = {
                                    "run_status": "in_progress",
                                    "event": event_type,
                                    "content": content
                                }
                                conn.send(json.dumps(fusion_call))


                            elif event_type == "thread.run.step.in_progress":
                                #print(data)
                                pass


                            elif event_type == "thread.message.delta":
                                #print(event.data)
                                delta_text = event.data.delta.content[0].text.value
                                message_id = event.data.id

                                content = {
                                    "message_id": message_id,
                                    "message": delta_text,
                                    "event": event_type,
                                }

                                fusion_call = {
                                    "run_status": "in_progress",
                                    "event": event_type,
                                    "content": content
                                }
                                conn.send(json.dumps(fusion_call))


                            elif event_type == "thread.run.step.delta":

                                function = event.data.delta.step_details.tool_calls[0].function
                                #print(function)

                                step_id = event.data.id

                                content = {
                                    "step_id": step_id,
                                    "function_name": function.name,
                                    "function_args": function.arguments,
                                    "function_output": function.output,
                                    "event": event_type,
                                }

                                fusion_call = {
                                    "run_status": "in_progress",
                                    "event": event_type,
                                    "content": content
                                }

                                conn.send(json.dumps(fusion_call))

                            elif event_type == "thread.message.completed":
                                content = event.data.content
                                for content_block in content:
                                    text = content_block.text.value
                                    message_text += text


                            elif event_type == "thread.run.requires_action":
                                print("THREAD.RUN.REQUIRES_ACTION")
                                print(event.data.required_action)

                                tool_calls = event.data.required_action.submit_tool_outputs.tool_calls
                                #print(tool_calls)

                                # return data for all tool calls in a step
                                tool_call_results = []
                                for tool_call in tool_calls:
                                    #tool_call_status

                                    function_name = tool_call.function.name
                                    function_args = tool_call.function.arguments

                                    if function_name == None:
                                        continue

                                    print(f"    CALL TOOL: {function_name}, {function_args}")

                                    fusion_call = {
                                        "run_status": self.run.status,
                                        "response_type": "tool_call",
                                        "event": event_type,
                                        "function_name": function_name,
                                        "function_args": function_args,
                                    }

                                    conn.send(json.dumps(fusion_call))

                                    # Fusion360 function results
                                    function_result = conn.recv()

                                    tool_call_results.append({
                                        "tool_call_id" : tool_call.id,
                                        "output": function_result
                                    })

                                    print(f"    FUNC RESULTS: {function_result}")

                                ## submit results for all tool calls in step
                                self.stream = self.submit_tool_call(tool_call_results)
                                print("TOOL CALL RESUTS FINISHED")


                            elif event_type == "thread.run.step.completed":
                                #print(event.data)

                                step_details = event.data.step_details
                                step_type = step_details.type

                                # skip response for mesage completion
                                if step_type == "message_creation":
                                    continue

                                function = step_details.tool_calls[0].function
                                #print(function)

                                step_id = event.data.id

                                content = {
                                    "step_id": step_id,
                                    "function_name": function.name,
                                    "function_args": function.arguments,
                                    "function_output": function.output,
                                    "event": event_type,
                                }

                                fusion_call = {
                                    "run_status": "in_progress",
                                    "event": event_type,
                                    "content": content
                                }

                                conn.send(json.dumps(fusion_call))


                            elif event_type == "thread.run.completed":
                                print("THREAD.RUN.COMPLETED")
                                #print(event.data)

                                fusion_call = {
                                    "run_status": "thread.run.completed",
                                    "response_type": "message",
                                    "event": event_type,
                                    "text": message_text
                                }

                                conn.send(json.dumps(fusion_call))





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


    def parse_stream(self, stream):

        for event in stream:

            event_type = event.event
            print(event_type)

            if event_type == "thread.message.completed":
                print("THREAD.MESSAGE.COMPLETED")
                print(event.data.content.text.value)

            elif event_type == "thread.run.requires_action":
                print("THREAD.RUN.REQUIRES_ACTION")
                print(event.data)

            elif event_type == "thread.run.step.completed":
                print("THREAD.RUN.STEP.COMPLETED")
                #print(event.data)

            elif event_type == "thread.run.completed":
                print("THREAD.RUN.COMPLETED")
                #print(event.data)



    def create_run(self):
        """create initial run"""

        stream = self.client.beta.threads.runs.create(
            thread_id=self.thread_id,
            assistant_id=self.assistant_id,
            stream=True
        )
        return stream


    def run_status(self):
        """get run status"""
        # get run status
        run = self.client.beta.threads.runs.retrieve(
            thread_id=self.thread_id,
            run_id=self.run_id,
        )

        return run



    def submit_tool_call(self, response_list: list):
        """
        send tool call responses
        response_list : list of dicts, each dict containg tool_call id and output
        """

        # function reply
        stream = self.client.beta.threads.runs.submit_tool_outputs(
            thread_id=self.thread_id,
            run_id=self.run_id,
            tool_outputs=response_list,
            stream=True,
        )

        return stream





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


    def cancel_run(self):
        run = self.client.beta.threads.runs.cancel(
          thread_id=self.thread_id,
          run_id=self.run_id
        )
        print('RUN CANCEL')




if __name__ == "__main__":

    assistant = Assistant(assistant_id =ASSISTANT_ID)
    assistant.start_server()
    #assistant.update_tools()
























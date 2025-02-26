
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


import whisper
import pyaudio
import wave


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

print(f"RELOADED: {__name__.split('%2F')[-1]}")


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

        #self.audio_interface = AudioInterface()

        # TODO eventualy, user should be able to restart thred from Fusion
        # start assistant thread (conversation)
        #self.start_thread()

        self.thread_started = False;

        # run local process server, how Fusion connects
        #self.start_server()
        #self.system_instructions_path = "system_instructions/system_instructions.txt"
        #self.selected_model = "gpt-4o"

        # store incomplete tool call ids, during an Exception in
        # the Fusion program, we can still respond to theese tool calls
        # and continue the thread
        self.pending_tool_calls = {}

        # whisper model size
        model_size = "base"
        #self.model = whisper.load_model(model_size)  # Load the selected model

    def start_record(self, conn):
        """
        Records audio from the default input device and saves it as a WAV file.
        :param filename: The name of the output WAV file.
        :param duration: Duration of the recording in seconds.
        :param sample_rate: Sample rate in Hz.
        :param chunk_size: Number of frames per buffer.
        :param channels: Number of audio channels (1 for mono, 2 for stereo).
        :param format: pyaudio format (default: pyaudio.paInt16).
        """

        filename="output.wav"
        sample_rate=44100
        chunk_size=1024
        channels=1
        audio_format=pyaudio.paInt32 #pyaudio.paInt32
        audio = pyaudio.PyAudio()

        # Open stream
        stream = audio.open(format=audio_format,
                            channels=channels,
                            rate=sample_rate,
                            input=True,
                            frames_per_buffer=chunk_size)

        fusion_call = {
            "content": "recording_started"
        }
        conn.send(json.dumps(fusion_call))

        frames = []

        #self.record = True
        while True:
            data = stream.read(chunk_size)
            frames.append(data)

            if conn.poll():
                # wait for message from user
                message_raw = conn.recv()
                message = json.loads(message_raw)
                print(f"conn.poll: {message}")

                break


        print("Recording finished.")

        # Stop and close the stream
        stream.stop_stream()
        stream.close()
        audio.terminate()

        # Save the recorded data as a WAV file
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(audio.get_sample_size(audio_format))
            wf.setframerate(sample_rate)
            wf.writeframes(b''.join(frames))

        print(f"Audio recorded and saved to {filename}")
        return self.transcribe_audio()


    def transcribe_audio(self, filename="output.wav"):
        """
        Transcribes an audio file using OpenAI's Whisper model.
        :param filename: The path to the audio file to transcribe.
        :param model_size: The size of the Whisper model to use (tiny, base, small, medium, large).
        :return: The transcribed text.
        """
        print(f"Transcribing {filename}...")
        result = self.model.transcribe(filename, language='en', fp16=False)

        text = result["text"]
        print("Transcription completed:")
        print(text)
        return text


    def format_str(self, string, n_char):
        """uniform print spacing """
        string = str(string)
        spacer_len = max(n_char - len(string), 0)
        spacer = " " *spacer_len 
        return f"{string}{spacer}"

    def get_available_system_instructions(self):
        """
        List available system instructions in the system
        """
        instructions = os.listdir("./system_instructions")
        return instructions

    def get_available_models(self):
        """
        List available Assistant models,
        This partially depends on on user payment tier
        """
        models_resp = self.client.models.list()
        models = models_resp.data
        model_ids = [m.id for m in models]
        return model_ids


    def update_settings(self, model_settings):
        """
        update assistant tools, and initial prompt instructions
        """

        #print(f"model_settings:  {model_settings}")
        #model_settings = json.loads(model_settings)

        model_name = model_settings["model_name"]
        instructions_path = model_settings["instructions_path"]
        tools = model_settings["tools"]
        reasoning_effort = model_settings["reasoning_effort"]

        # base assistant prompt
        with open(instructions_path) as f:
            instructions = f.read()
            instructions = instructions.strip()

        # functions
        tools = json.loads(tools)
        updated_tools = []
        for index, tool in enumerate(tools):
            updated_tools.append({"type": "function", "function": tool})
            print(f"{index}: {tool['name']}")
        try:
            updated_assistant = client.beta.assistants.update(
                self.assistant_id,
                model=model_name,
                instructions=instructions,
                tools=updated_tools,
                reasoning_effort=reasoning_effort,
                response_format="auto",
            )

            return {
                "id": updated_assistant.id,
                "name": updated_assistant.name,
                "model": updated_assistant.model,
                "created_at": updated_assistant.created_at,
            }

        except Exception as e:
            for index, tool in enumerate(tools):
                print(f"{index}: {tool['name']}")
            #print(f"ERROR: {e}")
            return f"Error: {e}"

    def start_thread(self):
        """
        start thread (conversation) with Assistant API
        """
        # create new thread
        self.thread = self.client.beta.threads.create()

        self.thread_id = self.thread.id

        # last run step
        self.run_steps = None
        self.thread_started = True
        print(f"Thread created: {self.thread.id}")


    def run(self, conn):
        """
        main server loop, called from "start server" accepts a multiprocess connection object
        """

        user_message_index = 0
        while True:
            print(f"\n{user_message_index}: WAITING FOR USER COMMAND...")
            user_message_index +=1

            # wait for message from user
            message_raw = conn.recv()
            message = json.loads(message_raw)

            message_type = message["message_type"]

            print(f"  MESSAGE RECEIVED:\n  {message_raw}")

            # handle system update calls, Assistant meta data
            # check if method exists on our Assistant class
            if message_type == "function_call":

                function_name = message.get("function_name")
                function_args = message.get("function_args", {})
                print(f"args: {function_args}")

                if not function_name:
                    results = f"Error: function_name is '{function_name}'"
                    print(results)
                elif not hasattr(self, function_name):
                    results = f"Error: {self} has no function '{function_name}'"
                    print(results)
                else:
                    function = getattr(self, function_name)
                    if not callable(function):
                        results = f"Error: '{function_name}' is not callable"
                        print(results)
                    else:
                        # call function
                        results = function(**function_args)

                conn.send(json.dumps(results))
                continue


            if message_type == "thread_update":
                message_text = message["content"]

            # start audio recording
            elif message_type == "start_record":
                # stop_record handled in self.start_record poll loop
                audio_text = self.start_record(conn)
                fusion_call = { "content": audio_text }
                conn.send(json.dumps(fusion_call))
                continue

            # start assistant thread
            if self.thread_started == False:
                self.start_thread()

            # add message to thread
            self.add_message(message_text)

            # once message(s) are added, run
            self.stream = self.create_run()

            event_type = ""
            message_text = ""
            delta_count = 0
            thread_start = 0

            # TODO condense much of this
            while event_type != "thread.run.completed":
                print(f"THREAD START")
                thread_start +=1

                if thread_start > 20:
                    return

                for event in self.stream:
                    event_type = event.event
                    print(event_type)
                    thread_start = 0
                    data = event.data

                    fusion_call = None
                    if event_type == "thread.run.created":
                        # set run id for tool call result calls
                        self.run = event.data
                        self.run_id = event.data.id

                        content = {
                            "run_id": self.run_id,
                        };

                        fusion_call = {
                            "run_status": "in_progress",
                            "event": event_type,
                            "content": content
                        }
                        #conn.send(json.dumps(fusion_call))

                    elif event_type == "thread.message.created":
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

                        #conn.send(json.dumps(fusion_call))

                    elif event_type == "thread.run.step.created":
                        step_type = data.type

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
                        #conn.send(json.dumps(fusion_call))


                    elif event_type == "thread.run.step.in_progress":
                        pass


                    elif event_type == "thread.message.delta":
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
                        #conn.send(json.dumps(fusion_call))


                    elif event_type == "thread.run.step.delta":

                        try:
                            function = event.data.delta.step_details.tool_calls[0].function

                            # tool call is not None on first delta  
                            tool_call_id = event.data.delta.step_details.tool_calls[0].id

                            tool_call_len = len(event.data.delta.step_details.tool_calls)

                            # TODO
                            if tool_call_len != 1:
                                print( event.data.delta.step_details.tool_calls)
                                print("CHECK TOOL CALL LEN\n\n\n\n\n")
                                return

                        except Exception as e:
                            print(e)
                            continue

                        step_id = event.data.id

                        content = {
                            "step_id": step_id,
                            "tool_call_id": tool_call_id,
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

                        delta_count +=1

                    elif event_type == "thread.message.completed":
                        content = event.data.content
                        delta_count = 0

                    elif event_type == "thread.run.requires_action":

                        tool_calls = event.data.required_action.submit_tool_outputs.tool_calls

                        # return data for all tool calls in a step
                        tool_call_results = []

                        for tool_call in tool_calls:

                            tool_call_id = tool_call.id
                            function_name = tool_call.function.name
                            function_args = tool_call.function.arguments

                            if function_name == None:
                                continue
                            print(f"    CALL TOOL: {function_name}, {function_args}")

                            fusion_call = {
                                "run_status": self.run.status,
                                "response_type": "tool_call",
                                "event": event_type,
                                "tool_call_id": tool_call_id,
                                "function_name": function_name,
                                "function_args": function_args,
                            }

                            # set tool call status in case of Exception during tool call
                            self.pending_tool_calls[tool_call_id] = "in_progress"

                            conn.send(json.dumps(fusion_call))
                            # Fusion360 function results
                            function_result = conn.recv()

                            tool_call_results.append({
                                "tool_call_id" : tool_call.id,
                                "output": function_result
                            })

                            # remove tool_cal_id after successful completion 
                            self.pending_tool_calls.pop(tool_call_id)


                            print(f"    FUNC RESULTS: {function_result}")

                        ## submit results for all tool calls in step
                        self.stream = self.submit_tool_call(tool_call_results)
                        print("TOOL CALL RESUTS FINISHED")
                        continue

                    elif event_type == "thread.run.step.completed":
                        delta_count = 0

                        step_details = event.data.step_details
                        step_type = step_details.type

                        # skip response for mesage completion
                        if step_type == "message_creation":
                            continue

                        try:
                            function = step_details.tool_calls[0].function
                        except Exception as e:
                            print(f"Error: thread.run.step.completed: {e}")
                            continue
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

                    elif event_type == "thread.run.completed":
                        print("THREAD.RUN.COMPLETED")
                        #print(event.data)

                        fusion_call = {
                            "run_status": "thread.run.completed",
                            "response_type": "message",
                            "event": event_type,
                            "text": message_text
                        }


                    if fusion_call != None:
                        conn.send(json.dumps(fusion_call))


    def start_server(self):
        # start run on local host, Fusion client must connect to this address
        address = ('localhost', 6000) # family is deduced to be 'AF_INET'

        while True:
            try:
                # Multiprocess server
                with Listener(address, authkey=b'fusion260') as listener:
                    print(f"WAITING FOR FUSION 360 TO CONNECT...")
                    # Fusion 360 Add-In connect here
                    with listener.accept() as conn:
                        print("CONNECTION ACCEPTED FROM", listener.last_accepted)
                        self.run(conn)

            except Exception as e:
                print(f"ERROR: {e} {traceback.format_exc()}")
                print(f"{traceback.format_exc()}")

                print(f"\nPENDING TOOL CALLS: {self.pending_tool_calls}")
                print(f"RETRYING CONNECTION...")
                time.sleep(1)


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

            if event_type == "thread.message.completed":
                print("THREAD.MESSAGE.COMPLETED")
                print(event.data.content.text.value)

            elif event_type == "thread.run.requires_action":
                print("THREAD.RUN.REQUIRES_ACTION")
                #print(event.data)

            elif event_type == "thread.run.step.completed":
                print("THREAD.RUN.STEP.COMPLETED")

            elif event_type == "thread.run.completed":
                print("THREAD.RUN.COMPLETED")

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
        response_list : list of dicts, each dict contains tool_call id and output
        """

        # function reply
        run = self.client.beta.threads.runs.submit_tool_outputs(
            thread_id=self.thread_id,
            run_id=self.run_id,
            tool_outputs=response_list
        )

        print(f"RESP RUN STATUS: run_id: {run.id}, status: {run.status}")


    def cancel_run(self):
        run = self.client.beta.threads.runs.cancel(
            thread_id=self.thread_id,
            run_id=self.run_id
        )
        print("RUN CANCEL")




if __name__ == "__main__":

    assistant = Assistant(assistant_id =ASSISTANT_ID)
    assistant.start_server()
























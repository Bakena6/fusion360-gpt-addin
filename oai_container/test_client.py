

from multiprocessing.connection import Client
from array import array
import json
import time



class GptClient:

    def __init__(self):

        self.connect()
        time.sleep(1)
        self.start()


    def call_function(self, name, function_args):
        """
        call function passed from Assistants API
        """
        args = {}
        if function_args != None:
            func_args = json.loads(function_args)

        print(f"CALL FUNCTION: {name}, {func_args}")

        function = getattr(self, name, None )

        if callable(function):
            result = function(**func_args)
        else:
            result = ""

        return result

    def connect(self):
        """connect to assistant manager class on seperate process"""

        address = ('localhost', 6000)
        self.conn = Client(address, authkey=b'fusion260')
            #self.conn = conn


    def start(self):
        for i in range(10):
            print(f"{i}: RUN")

            # user message, natural language
            message = input("enter message: ")
            print(f"  sending mesage: {message}")

            message_confirmation = self.conn.send(message)
            print(f"  message sent,  waiting for result...")

            # continue to run as loong thread is open
            run_complete = False
            while run_complete == False:

                # result from server
                api_result = self.conn.recv()
                api_result = json.loads(api_result)

                response_type = api_result["response_type"]
                run_status = api_result["run_status"]

                if response_type == "message":
                    print(f"message: {api_result}")

                elif response_type == "tool_call":

                    function_name = api_result["function_name"]
                    function_args = api_result["function_args"]

                    function_result = self.call_function(function_name, function_args)
                    #time.sleep(1)
                    self.conn.send(function_result)

                if run_status == "completed":
                    run_complete = True






    def get_root_component_name(self):
        return "rootComp"

    def rename_component(self, component, new_name):
        return new_name

    def move_component_to_point(self, component_name, new_point):
        return True

    def find_component_by_name(self, function_name):
        return "subComp"

    def create_new_component(self, parent_component_name, component_name):
        return "comp1"

    def create_sketch(self, component_name, sketch_name, sketch_plane="xy"):
        return sketch_name


if __name__ == "__main__":

    client = GptClient()








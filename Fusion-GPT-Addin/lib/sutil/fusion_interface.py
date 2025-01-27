import adsk.core
import adsk.fusion
import adsk.cam
import traceback
import sys
import math
import os
import json
import inspect

from multiprocessing.connection import Client
from array import array
import time

import functools

from ... import config
from ...lib import fusion360utils as futil

# send info to html palette
PALETTE_ID = config.palette_id
app = adsk.core.Application.get()
ui = app.userInterface
palette = ui.palettes.itemById(PALETTE_ID)

def print(string):
    """redefine print for fusion env"""
    futil.log(str(string))


class GptClient:
    """
    connects to command server running on seperate process
    """

    def __init__(self, fusion_interface):
        """
        fusion_interface : class inst whose methods call Fusion API
        """
        self.fusion_interface = fusion_interface
        self.app = adsk.core.Application.get()

        # current connection status
        self.connected = False

        # tool call history
        self.call_history = {}
        #self.connect()

    def connect(self):
        """
        connect to assistant manager class on seperate process
        """
        address = ('localhost', 6000)
        self.conn = Client(address, authkey=b'fusion260')
        self.connected = True;


    def sendToBrowser(self, function_name, data):
        json_data = json.dumps(data)
        # create run output section in html
        palette.sendInfoToHTML(function_name, json_data)

    def upload_tools(self):
        """
        upload tools to assistant
        """

        if self.connected == False:
            self.connect()

        tools = self.fusion_interface.get_docstr()

        message = {
            "message_type": "tool_update",
            "content": tools
        }
        message = json.dumps(message)

        message_confirmation = self.conn.send(message)

        print(f"  message sent,  waiting for result...")



    def send_message(self, message):
        """send message"""

        if self.connected == False:
            self.connect()

        print(f"  sending mesage: {message}")

        message = {"message_type": "thread_update", "content": message}
        message = json.dumps(message)

        message_confirmation = self.conn.send(message)
        print(f"  message sent,  waiting for result...")

        # continue to run as loong thread is open
        run_complete = False
        while run_complete == False:

            # result from server
            api_result = self.conn.recv()
            api_result = json.loads(api_result)

            response_type = api_result.get("response_type")
            event_type = api_result.get("event")
            run_status = api_result.get("run_status")

            content = api_result.get("content")

            # streaming call outputs
            if event_type == "thread.run.created":
                print(event_type)
                print(content)
                self.sendToBrowser("runCreated", content)

            # streaming call outputs
            elif event_type == "thread.run.step.created":
                self.sendToBrowser("stepCreated", content)

            # streaming call outputs
            elif event_type == "thread.message.created":
                self.sendToBrowser("messageCreated", content)

            # streaming call outputs
            elif event_type == "thread.message.delta":
                self.sendToBrowser("messageDelta", content)

            #elif event_type in ["thread.run.step.delta", "thread.run.step.completed"]:
            elif event_type in ["thread.run.step.delta"]:
                self.sendToBrowser("stepDelta", content)

            # TODO, use event type not response type
            elif response_type == "tool_call":

                function_name = api_result["function_name"]
                function_args = api_result["function_args"]
                function_result = self.call_function(function_name, function_args)
                message = {"message_type": "thread_update", "content": function_result}
                message = json.dumps(message)
                self.conn.send(function_result)

            # thread complete break loop
            if run_status == "thread.run.completed":
                run_complete = True

            adsk.doEvents()

        return api_result




    def call_function(self, name, function_args):
        """
        call function passed from Assistants API
        """

        if function_args == "":
            function_args = None

        #if function_args != None:
        if function_args != None:
            function_args = json.loads(function_args)

        print(f"CALL FUNCTION: {name}, {function_args}")

        # check of FusionInterface inst has requested method
        function = getattr(self.fusion_interface, name, None )

        if callable(function):
            if function_args == None:
                result = function()
            else:
                result = function(**function_args)

        else:
            result = ""

        return result






class FusionInterface:
    """
    interface between Fusion360 api and OpenAI Assistant
    methonds in this class are made avilable to the OpenAI Assistants API
    via the GptClient class
    """

    def __init__(self, app, ui):
        self.app = app
        self.ui = ui
        self.design = adsk.fusion.Design.cast(self.app.activeProduct)

        # method collections
        submodules = [
            SketchMethods(),
            StateData(),
            SetData()
        ]

        fusion_methods = {}
        for submod in submodules:
            for method_name, method in submod.methods.items():
                #print(method_name)
                # add method from container classes to main interface class
                setattr(self, method_name, method)


    def get_tools(self):
        """
        creates list fusion interface functions
        """
        methods = {}
        self.get_docstr()

        for attr_name in dir(self):
            # ignore functions that don't directly interface with fusion workspace
            if attr_name in ["__init__", "get_tools", "fusion_call"]:
                continue
            attr = getattr(self, attr_name)

            if callable(attr) == False:
                continue

            if str(attr.__class__) == "<class 'method'>":

                methods[attr_name] = {}

                sig = inspect.signature(attr)
                attr = inspect.unwrap(attr)

                default_vals = inspect.getfullargspec(attr).defaults

                if default_vals != None:
                    n_default_vals = len(default_vals)
                else:
                    n_default_vals = 0


                param_dict = {}
                for index, param_name in enumerate(sig.parameters):
                    annotation = sig.parameters.get(param_name).annotation

                    if index < n_default_vals:
                        default_val = default_vals[index]
                    else:
                        default_val = None

                    param_info_dict = {
                        "type": str(annotation),
                        "default_val": default_val
                    }

                    #param_info_dict

                    param_dict[param_name] = param_info_dict

                methods[attr_name] = param_dict

        return methods

    def get_docstr(self):
        """
        creates list fusion interface functions
        """

        method_list = []
        index = 0
        for attr_name in dir(self):

            # ignore functions that don't directly interface with fusion workspace
            if attr_name in ["__init__", "get_tools", "fusion_call", "get_docstr", "save_assistant_functions" ]:
                continue
            attr = getattr(self, attr_name)

            if callable(attr) == False:
                continue

            if str(attr.__class__) == "<class 'method'>":
                sig = inspect.signature(attr)
                attr = inspect.unwrap(attr)
                #print(f"{index}: {attr_name}")
                index += 1

                docstring = attr.__doc__

                json_method = json.loads(docstring)

                method_list.append(json_method)

        method_list = json.dumps(method_list, indent=4)

        self.tools_json = method_list

        return method_list


    def fusion_call(func):
        """
        Wraps fusion interface calls
        """
        # for retrieving wrapped function kwarg names
        @functools.wraps(func)
        def wrapper(self, *args, **kwds):

            self.app = adsk.core.Application.get()
            print("func start")
            result = func(self, *args, **kwds)
            #print(result)
            print("func end")
            return result

        return wrapper




class FusionSubmodule:
    """
    methods colletion
    """

    def __init__(self):
        self.methods = self._get_methods()


    def _get_methods(self):
        """
        creates list fusion interface functions
        """
        methods = {}

        for attr_name in dir(self):

            # ignore any method with leading underscore "_", e.g __init__, 
            # ignore functions that don't directly interface with fusion workspace
            if attr_name[0] == "_":
                continue

            attr = getattr(self, attr_name)

            if callable(attr) == False:
                continue

            if str(attr.__class__) == "<class 'method'>":
                methods[attr_name] = attr

        return methods



    def _find_component_by_name(self, component_name:str="comp1"):
        """
        called from methods, not Assistant directly
        """

        # Access the active design
        app = adsk.core.Application.get()
        design = adsk.fusion.Design.cast(app.activeProduct)
        rootComp = design.rootComponent

        # Find the target component
        targetComponent = None
        for occ in rootComp.allOccurrences:
            if occ.component.name == component_name:
                targetComponent = occ.component
                break

        #if not targetComponent:
        #    return f'Component "{component_name}" not found'

        return targetComponent


    def _find_sketch_by_name(self, component, sketch_name):

        # Find the target sketch
        targetSketch = None
        for sketch in component.sketches:
            if sketch.name == sketch_name:
                targetSketch = sketch
                break

        return targetSketch




class StateData(FusionSubmodule):
    """
    methods used by Realtime API to retrive state of Fusion document
    """
    def get_root_component_name(self):
        """
        {
            "name": "get_root_component_name",
            "description": "Retrieves the name of the root component in the current Fusion 360 design.",
            "parameters": {}
        }
        """
        try:
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)

            # Access the active design
            if design:
                # Return the name of the root component
                return design.rootComponent.name
            else:
                return None

        except Exception as e:
            return None


    def get_design_as_json(self) -> str:
        """
        {
          "name": "get_design_as_json",
          "description": "Collects information about the active Fusion 360 design (including components, bodies, sketches, joints, and nested occurrences) and returns a JSON-encoded string describing the entire structure.",
          "parameters": {
            "type": "object",
            "properties": {
            },
            "required": [],
            "returns": {
              "type": "string",
              "description": "A JSON-encoded string representing the structure of the current design, including name, bodies, sketches, joints, and nested occurrences for each component."
            }
          }
        }
        """

        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)

        if not app:
            return "{}"  # Return empty JSON object if no Application is found

        product = app.activeProduct
        if not product or not isinstance(product, adsk.fusion.Design):
            return "{}"  # Return empty JSON object if no active design

        design = adsk.fusion.Design.cast(product)

        # Recursively gather data for each component
        def get_component_data(component):
            comp_dict = {
                "name": component.name,
                "bodies": [],
                "sketches": [],
                "joints": [],
                "occurrences": []
            }

            # Collect bodies
            for body in component.bRepBodies:
                comp_dict["bodies"].append(body.name)

            # Collect sketches
            for sketch in component.sketches:
                comp_dict["sketches"].append(sketch.name)

            # Collect joints
            for joint in component.joints:
                comp_dict["joints"].append(joint.name)

            # Recursively gather data for all child occurrences
            for occ in component.occurrences:
                sub_comp = occ.component
                if sub_comp:
                    sub_comp_data = get_component_data(sub_comp)
                    comp_dict["occurrences"].append(sub_comp_data)

            return comp_dict

        # Build a dictionary that holds the entire design structure
        design_data = {
            "designName": design.rootComponent.name,
            "rootComponent": get_component_data(design.rootComponent)
        }

        # Convert dictionary to a JSON string with indentation
        return json.dumps(design_data, indent=4)

    def get_design_parameters_as_json(self) -> str:
        """
        {
            "name": "get_design_parameters_as_json",
            "description": "Collects all parameters from the active Fusion 360 design and returns a JSON-formatted string. Each parameter includes its name, unit, expression, numeric value, and comment. The resulting JSON structure contains an array of parameter objects, making it easy to review and utilize parameter data.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "returns": {
                    "type": "string",
                    "description": "A JSON-encoded string listing all parameters in the active design, including name, unit, expression, value, and comment for each parameter."
                }
            }
        }
        """

        app = adsk.core.Application.get()
        if not app:
            return json.dumps({"parameters": []})

        product = app.activeProduct
        # Ensure we have a Fusion Design
        if not product or not isinstance(product, adsk.fusion.Design):
            return json.dumps({"parameters": []})

        design = adsk.fusion.Design.cast(product)

        # Gather all parameters (this includes user parameters and model parameters)
        all_params = design.allParameters
        params_list = []

        for param in all_params:
            # Some parameters may not have a comment or expression.
            # We'll store empty strings if they're missing.
            #print(param)
            name = param.name
            unit = param.unit or ""
            expression = param.expression or ""
            value = param.value  # Numeric value
            comment = param.comment or ""

            params_list.append({
                "name": name,
                "unit": unit,
                "expression": expression,
                "value": value,
                "comment": comment
            })

        # Build the final JSON object
        data = {"parameters": params_list}

        # Convert to a JSON string
        return json.dumps(data, indent=4)

    def get_model_parameters_by_component_as_json(self) -> str:
        """
        {
            "name": "get_model_parameters_by_component_as_json",
            "description": "Gathers model parameters from each component in the current Fusion 360 design, organizing them in a hierarchical structure that matches the assembly structure. Model parameters include any input parameter to features or construction geometry (e.g., hole diameters, extrusion distances, etc.). Returns a JSON-encoded string with design and parameter details such as name, expression, unit, value, and comment, grouped by component and sub-component.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "returns": {
                    "type": "string",
                    "description": "A JSON-encoded string representing the hierarchical structure of the current design’s components and their associated model parameters."
                }
            }
        }
        """

        app = adsk.core.Application.get()
        if not app:
            return json.dumps({})

        product = app.activeProduct
        if not product or not isinstance(product, adsk.fusion.Design):
            return json.dumps({})

        design = adsk.fusion.Design.cast(product)
        root_comp = design.rootComponent

        def gather_component_parameters(component):
            """
            Recursively gathers model parameters for the specified component and its children.
            Returns a dictionary with the component name, its model parameters, and its children.
            """
            comp_dict = {
                "name": component.name,
                "modelParameters": [],
                "children": []
            }

            # Collect all ModelParameters from this component
            for model_param in component.modelParameters:
                param_info = {
                    "name": model_param.name,
                    "created_by": model_param.createdBy.name,
                    "role": model_param.role,
                    "unit": model_param.unit or "",
                    "expression": model_param.expression or "",
                    "value": model_param.value,      # The resolved numeric value
                    "comment": model_param.comment or ""
                }
                comp_dict["modelParameters"].append(param_info)

            # Recursively gather data for child occurrences (sub-components)
            for occurrence in component.occurrences:
                # Each occurrence references a component
                sub_comp = occurrence.component
                if sub_comp:
                    # Gather parameters for the child component
                    child_comp_dict = gather_component_parameters(sub_comp)
                    comp_dict["children"].append(child_comp_dict)

            return comp_dict

        # Build a dictionary that represents the entire design structure
        design_data = {
            "designName": design.rootComponent.name,
            "rootComponent": gather_component_parameters(root_comp)
        }

        # Convert dictionary to a JSON string
        return json.dumps(design_data, indent=4)


    def get_sketch_profiles(self, component_name: str = "comp1", sketch_name: str = "sketch1"):
        """
        {
            "name": "get_sketch_profiles",
            "description": "Retrieves all the profiles from a specified sketch within a specified component. Returns a JSON-like object containing each profile's area, center point, and areaIndex (with 0 being the largest profile).",
            "parameters": {
                "type": "object",
                "properties": {
                    "component_name": {
                        "type": "string",
                        "description": "The name of the component in the current design containing the sketch."
                    },
                    "sketch_name": {
                        "type": "string",
                        "description": "The name of the sketch inside the specified component."
                    }
                },
                "required": ["component_name", "sketch_name"],
                "returns": {
                    "type": "object",
                    "description": "A JSON-like dictionary with a 'profiles' key, listing each profile's area, centroid (x, y, z), and areaIndex sorted by descending area. If an error occurs, a string describing the error is returned instead."
                }
            }
        }
        """
        try:
            # Access the active design
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            # Use a local helper method to find the target component
            targetComponent = self._find_component_by_name(component_name)
            if not targetComponent:
                return f'Error: Component "{component_name}" not found.'

            # Use a local helper method to find the specified sketch
            targetSketch = self._find_sketch_by_name(targetComponent, sketch_name)
            if not targetSketch:
                return f'Error: Sketch "{sketch_name}" not found in component "{component_name}".'

            if not targetSketch.profiles or targetSketch.profiles.count == 0:
                return "No profiles found in the sketch."

            # Gather profile information (area and centroid)
            profile_data = []
            for profile in targetSketch.profiles:
                props = profile.areaProperties()
                area = props.area
                centroid = props.centroid
                profile_data.append({
                    "profile": profile,  # Storing the actual profile object (if needed)
                    "area": area,
                    "centroid": [centroid.x, centroid.y, centroid.z]
                })

            # Sort profiles by descending area
            profile_data.sort(key=lambda p: p["area"], reverse=True)

            # Create the final list of profile info for JSON-like output
            results = []
            for idx, data in enumerate(profile_data):
                results.append({
                    "areaIndex": idx,  # 0 = largest
                    "area": data["area"],
                    "centerPoint": data["centroid"]
                })

            # Return the JSON-like structure
            return json.dumps({ "profiles": results })

        except Exception as e:
            return f"Error: {e}"


class SketchMethods(FusionSubmodule):

    def create_sketch(self, component_name: str="comp1", sketch_name: str ="sketch1", sketch_plane: str ="xy"):
        """
            {
              "name": "create_sketch",
              "description": "Creates a sketch within a specified component on a specified plane in Fusion 360. The plane can be xy, xz, or yz.",
              "parameters": {
                "type": "object",
                "properties": {
                  "component_name": {
                    "type": "string",
                    "description": "The name of the component where the sketch will be created."
                  },
                  "sketch_name": {
                    "type": "string",
                    "description": "The name for the new sketch to be created."
                  },
                  "sketch_plane": {
                    "type": "string",
                    "enum": ["xy", "xz", "yz"],
                    "description": "The plane on which the sketch will be created. Possible values are 'xy', 'xz', 'yz'. Default is 'xy'."
                  }
                },
                "required": ["component_name", "sketch_name"],
                "returns": {
                  "type": "string",
                  "description": "A message indicating the success or failure of the sketch creation."
                }
              }
            }
        """

        try:
            # Access the active design
            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)
            rootComp = design.rootComponent

            # use base class method
            targetComponent = self._find_component_by_name(component_name)
            if not targetComponent:
                return f'Component "{component_name}" not found'

            # Determine the sketch plane
            if sketch_plane.lower() == "xz":
                plane = targetComponent.xZConstructionPlane
            elif sketch_plane.lower() == "yz":
                plane = targetComponent.yZConstructionPlane
            else:  # Default to XY plane
                plane = targetComponent.xYConstructionPlane

            # Create the sketch
            newSketch = targetComponent.sketches.add(plane)
            newSketch.name = sketch_name

            return f'Sketch "{sketch_name}" created successfully'

        except Exception as e:
            return f'Failed to create sketch: {e}'


    def create_rectangles_in_sketch(self, component_name: str="comp1", sketch_name: str="sketch1", center_point_list: list=[[1,1,0]], rectangle_size_list:list=[[2,4]]):
        """
        {
          "name": "create_rectangles_in_sketch",
          "description": "Creates rectangles in a specified sketch within a specified component in Fusion 360 using addCenterPointRectangle. Each rectangle is defined by a center point (from center_point_list) and a size (width, height) from rectangle_size_list. A corner point is calculated automatically from the center and half the width and height, and two distance dimensions (horizontal and vertical) are applied. The number of elemenets in center_point_list must be equal to the number of elements in rectangle_size_list",
          "parameters": {
            "type": "object",
            "properties": {
              "component_name": {
                "type": "string",
                "description": "The name of the component in the current design."
              },
              "sketch_name": {
                "type": "string",
                "description": "The name of the sketch inside the specified component."
              },
              "center_point_list": {
                "type": "array",
                "items": {
                  "type": "array",
                  "items": {
                    "type": "number"
                  },
                  "minItems": 3,
                  "maxItems": 3,
                  "description": "A list representing an XYZ point (x, y, z)."
                },
                "description": "A list of center points in 3D space for each rectangle to be created."
              },
              "rectangle_size_list": {
                "type": "array",
                "items": {
                  "type": "array",
                  "items": {
                    "type": "number"
                  },
                  "minItems": 2,
                  "maxItems": 2,
                  "description": "A list representing the width and height of the rectangle."
                },
                "description": "A list of [width, height] pairs, corresponding to each center point in center_point_list."
              }
            },
            "required": ["component_name", "sketch_name", "center_point_list", "rectangle_size_list"],
            "returns": {
              "type": "string",
              "description": "A message indicating the success or failure of the rectangle creation."
            }
          }
        }
        """

        try:


            # if dim list passed in as string from user input box
            if isinstance(center_point_list, str):
                center_point_list = json.loads(center_point_list)
            if isinstance(rectangle_size_list, str):
                rectangle_size_list = json.loads(rectangle_size_list)


            # Validate input lengths
            if len(center_point_list) != len(rectangle_size_list):

                center_point_len = len(center_point_list)
                rectangle_size_len = len(rectangle_size_list)

                message = f"The lengths of center_point_list ({center_point_len}) and rectangle_size_list ({rectangle_size_len}) must be equal."

                return message

            # Access the active design
            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return "Error: No active Fusion 360 design found."

            root_comp = design.rootComponent

            # Find the target component
            targetComponent = None
            for occ in root_comp.allOccurrences:
                if occ.component.name == component_name:
                    targetComponent = occ.component
                    break

            # use base class method
            targetComponent = self._find_component_by_name(component_name)
            if not targetComponent:
                return f'Component "{component_name}" not found.'

            # Find the target sketch
            targetSketch = None
            for sketch in targetComponent.sketches:
                if sketch.name == sketch_name:
                    targetSketch = sketch
                    break

            if not targetSketch:
                return f'Sketch "{sketch_name}" not found in component "{component_name}".'

            # Create rectangles in the sketch
            for center_point, size in zip(center_point_list, rectangle_size_list):
                width, height = size[0], size[1]

                # Create the center point 3D object
                center3D = adsk.core.Point3D.create(center_point[0], center_point[1], center_point[2])

                # Calculate the corner point (relative to center)
                # For an axis-aligned rectangle, corner is (center.x + width/2, center.y + height/2, center.z).
                corner3D = adsk.core.Point3D.create(
                    center_point[0] + width / 2.0,
                    center_point[1] + height / 2.0,
                    center_point[2]
                )

                # Create the rectangle using addCenterPointRectangle
                rectangleLines = targetSketch.sketchCurves.sketchLines.addCenterPointRectangle(center3D, corner3D)

                # The addCenterPointRectangle returns a list of four SketchLine objects.
                # Typically:
                #   lines[0]: horizontal line (top or bottom)
                #   lines[1]: vertical line (left or right)
                #   lines[2]: horizontal line (the other top/bottom)
                #   lines[3]: vertical line (the other left/right)

                dimensions = targetSketch.sketchDimensions

                # Dimension the first horizontal line as the 'width'
                horizontalLine = rectangleLines[0]
                dimPointWidth = adsk.core.Point3D.create(center_point[0], center_point[1] - 1, center_point[2])
                dimWidth = dimensions.addDistanceDimension(
                    horizontalLine.startSketchPoint,
                    horizontalLine.endSketchPoint,
                    adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
                    dimPointWidth
                )

                # Dimension the first vertical line as the 'height'
                verticalLine = rectangleLines[1]
                dimPointHeight = adsk.core.Point3D.create(center_point[0] - 1, center_point[1], center_point[2])
                dimHeight = dimensions.addDistanceDimension(
                    verticalLine.startSketchPoint,
                    verticalLine.endSketchPoint,
                    adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
                    dimPointHeight
                )

                # Optionally set exact values of the parameters to fix the rectangle size
                # Uncomment if you need these to be parametric at exactly 'width' and 'height':
                #
                # dimWidth.parameter.value = width
                # dimHeight.parameter.value = height

            return f'Rectangles created in sketch "{sketch_name}" using center-point rectangle method.'

        except Exception as e:

            return f'Failed to create rectangles in sketch: {e}'

    def create_circles_in_sketch(self, component_name:str="comp1", sketch_name:str="sketch1", point_list:str=[[1,1,0]], circle_diameter_list:list=[10]):
        """
        {
          "name": "create_circles_in_sketch",
          "description": "Creates circles in a specified sketch within a specified component in Fusion 360. Each circle is created at a point provided in the point_list, with its diameter specified by the corresponding element in circle_diameter_list.",
          "parameters": {
            "type": "object",
            "properties": {
              "component_name": {
                "type": "string",
                "description": "The name of the component in the current design."
              },
              "sketch_name": {
                "type": "string",
                "description": "The name of the sketch inside the specified component."
              },
              "point_list": {
                "type": "array",
                "items": {
                  "type": "array",
                  "items": {
                    "type": "number"
                  },
                  "minItems": 3,
                  "maxItems": 3,
                  "description": "A list representing an XYZ point."
                },
                "description": "A list of lists, each representing an XYZ point (x, y, z) where a circle will be created."
              },
              "circle_diameter_list": {
                "type": "array",
                "items": {
                  "type": "number"
                },
                "description": "A list of diameters for the circles, corresponding to each point in point_list."
              }
            },
            "required": ["component_name", "sketch_name", "point_list", "circle_diameter_list"],
            "returns": {
              "type": "string",
              "description": "A message indicating the success or failure of the circle creation."
            }
          }
        }
        """
        try:
            # Validate the lengths of point_list and circle_diameter_list
            if len(point_list) != len(circle_diameter_list):
                return "The lengths of point_list and circle_diameter_list must be equal."

            # Access the active design
            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)
            rootComp = design.rootComponent

            # use base class method
            targetComponent = self._find_component_by_name(component_name)
            if not targetComponent:
                return f'Component "{component_name}" not found.'

            # Find the target sketch
            targetSketch = None
            for sketch in targetComponent.sketches:
                if sketch.name == sketch_name:
                    targetSketch = sketch
                    break

            if not targetSketch:
                return f'Sketch "{sketch_name}" not found in component "{component_name}"'

            print("abc")
            # Create circles in the sketch
            for point, diameter in zip(point_list, circle_diameter_list):
                print(point)

                centerPoint = adsk.core.Point3D.create(point[0], point[1], point[2])

                # circle entity
                entity = targetSketch.sketchCurves.sketchCircles.addByCenterRadius(centerPoint, diameter / 2)
                # offset the text label
                textPoint = adsk.core.Point3D.create(point[0]+1, point[1]+1, point[2])

                dimensions = targetSketch.sketchDimensions

                circleDimension = dimensions.addDiameterDimension(entity, textPoint)

            return f'Circles created in sketch "{sketch_name}"'

        except Exception as e:
            return f'Failed to create circles in sketch: {e}'


    def create_polygon_in_sketch(self, parent_component_name:str="comp1", sketch_name:str="sketch1", point_list:list=[[0,0,0], [0,1,0], [1,2,0]]):
        """
        {
          "name": "create_polygon_in_sketch",
          "description": "Creates a polygon in an existing sketch within a specified parent component in Fusion 360. The polygon is formed by connecting a series of points provided in the point_list.",
          "parameters": {
            "type": "object",
            "properties": {
              "parent_component_name": {
                "type": "string",
                "description": "The name of the parent component where the polygon will be created."
              },
              "sketch_name": {
                "type": "string",
                "description": "The name of the existing sketch where the polygon will be created."
              },
              "point_list": {
                "type": "array",
                "items": {
                  "type": "array",
                  "items": {
                    "type": "number"
                  },
                  "minItems": 2,
                  "maxItems": 2,
                  "description": "A tuple representing an XY point (x, y)."
                },
                "description": "A list of tuples, each representing an XY point (x, y) to be included in the polygon."
              }
            },
            "required": ["parent_component_name", "sketch_name", "point_list"],
            "returns": {
              "type": "string",
              "description": "A message indicating the success or failure of the polygon creation."
            }
          }
        }
        """
        try:
            # Access the active design
            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)
            rootComp = design.rootComponent

            # Find the parent component
            parentComponent = None
            for occ in rootComp.allOccurrences:
                if occ.component.name == parent_component_name:
                    parentComponent = occ.component
                    break

            # use base class method
            parentComponent = self._find_component_by_name(parent_component_name)
            if not parentComponent:
                return f'Parent component "{parent_component_name}" not found'

            # Find the existing sketch
            targetSketch = None
            for sketch in parentComponent.sketches:
                if sketch.name == sketch_name:
                    targetSketch = sketch
                    break

            if not targetSketch:
                return f'Sketch "{sketch_name}" not found in component "{parent_component_name}"'

            # Add points and lines to the sketch to form the polygon
            for i in range(len(point_list)):
                start_point = adsk.core.Point3D.create(point_list[i][0], point_list[i][1], 0)
                end_point_index = (i + 1) % len(point_list)
                end_point = adsk.core.Point3D.create(point_list[end_point_index][0], point_list[end_point_index][1], 0)
                targetSketch.sketchCurves.sketchLines.addByTwoPoints(start_point, end_point)


            return f'Polygon created in sketch "{sketch_name}"'

        except Exception as e:
            return f'Failed to create polygon in sketch: {e}'


    def extrude_largest_profile(self, component_name:str="comp1", sketch_name:str="sketch1", extrusion_distance:float=1.0):
        """
        {
            "name": "extrude_largest_profile",
            "description": "Selects the largest profile in a specified sketch within a component and extrudes it by a given distance. The component and sketch are identified by their names.",
            "parameters": {
              "type": "object",
              "properties": {
                "component_name": {
                  "type": "string",
                  "description": "The name of the component in the current design containing the sketch."
                },
                "sketch_name": {
                  "type": "string",
                  "description": "The name of the sketch inside the specified component."
                },
                "extrusion_distance": {
                  "type": "number",
                  "description": "The distance to extrude the selected profile, in the current units of the design."
                }
              },
              "required": ["component_name", "sketch_name", "extrusion_distance"]
            }
        }
        """
        try:
            # Access the active design
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            rootComp = design.rootComponent

            # use base class method to select component obj
            targetComponent = self._find_component_by_name(component_name)
            if not targetComponent:
                return f'Component "{component_name}" not found'

            # use base class method to select sketch obj
            targetSketch = self._find_sketch_by_name(targetComponent, sketch_name )
            if not targetSketch:
                return f'Sketch "{sketch_name}" not found in component "{component_name}"'

            # Find the largest profile
            largestProfile = None
            maxArea = 0
            for profile in targetSketch.profiles:
                area = profile.areaProperties().area
                if area > maxArea:
                    maxArea = area
                    largestProfile = profile

            if not largestProfile:
                return 'No profiles found in the sketch'

            # Create an extrusion
            extrudes = targetComponent.features.extrudeFeatures
            extrudeInput = extrudes.createInput(largestProfile, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
            distance = adsk.core.ValueInput.createByReal(extrusion_distance)
            extrudeInput.setDistanceExtent(False, distance)
            extrudes.add(extrudeInput)

            return 'extruded profile'

        except Exception as e:
            return 'Failed to extrude profile'

    def extrude_profiles_in_sketch(self, component_name: str="comp1", sketch_name: str="sketch1", profiles_list: list=[[0,1], [1,2]]) -> str:
        """
        {
          "name": "extrude_profiles_in_sketch",
          "description": "Extrudes multiple profiles in a specified sketch by different amounts. The profiles are indexed by descending area, where 0 refers to the largest profile. Each item in profiles_list is [profileIndex, extrudeDistance].",
          "parameters": {
            "type": "object",
            "properties": {
              "component_name": {
                "type": "string",
                "description": "The name of the component in the current design containing the sketch."
              },
              "sketch_name": {
                "type": "string",
                "description": "The name of the sketch inside the specified component containing the profiles."
              },
              "profiles_list": {
                "type": "array",

                "items": {
                  "type": "array",
                  "items": {
                    "type": "number"
                  },
                  "minItems": 2,
                  "maxItems": 2,
                  "description": "Each element is [profileIndex, extrudeDistance]. profileIndex is an integer referencing the area-sorted profile, and extrudeDistance is a number specifying how far to extrude."
                },
                "description": "A list of profileIndex / extrudeDistance pairs specifying which profiles to extrude and by how much."
              }
            },
            "required": ["component_name", "sketch_name", "profiles_list"]
          }
        }
        """
        try:
            # Access the active design.
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)

            # Locate the target component by name (using a local helper method).
            targetComponent = self._find_component_by_name(component_name)
            if not targetComponent:
                return f'Error: Component "{component_name}" not found.'

            # Locate the sketch by name (within the target component).
            targetSketch = self._find_sketch_by_name(targetComponent, sketch_name)
            if not targetSketch:
                return f'Error: Sketch "{sketch_name}" not found in component "{component_name}".'

            if not targetSketch.profiles or targetSketch.profiles.count == 0:
                return f'Sketch "{sketch_name}" has no profiles to extrude.'

            # Collect and sort profiles by area in descending order (largest first).
            profile_info = []
            for prof in targetSketch.profiles:
                props = prof.areaProperties()
                profile_info.append((prof, props.area))
            profile_info.sort(key=lambda x: x[1], reverse=True)

            # Extrude each profile according to profiles_list.
            results = []
            extrudes = targetComponent.features.extrudeFeatures
            for pair in profiles_list:
                if not isinstance(pair, list) or len(pair) < 2:
                    results.append("Error: Invalid profiles_list entry (expected [profileIndex, distance]).")
                    continue

                profileIndex, extrudeDist = pair[0], pair[1]

                # Check the valid index range.
                if profileIndex < 0 or profileIndex >= len(profile_info):
                    results.append(f"Error: Invalid profile index {profileIndex}.")
                    continue

                selectedProfile = profile_info[profileIndex][0]

                try:
                    distanceVal = adsk.core.ValueInput.createByReal(float(extrudeDist))
                    extInput = extrudes.createInput(
                        selectedProfile,
                        adsk.fusion.FeatureOperations.NewBodyFeatureOperation
                    )

                    # Set the extent as a one-side distance.
                    extInput.setDistanceExtent(False, distanceVal)
                    extrudes.add(extInput)
                    results.append(f"Profile index {profileIndex} extruded by {extrudeDist}.")
                except Exception as e:
                    results.append(f"Error: Could not extrude profile {profileIndex}. Reason: {e}")

            # Combine all messages.
            return "\n".join(results)

        except Exception as e:
            return f"Error: An unexpected exception occurred: {e}"



class SetData(FusionSubmodule):
    ### Internal ###


    ### =================== CREEATE OBJECTS ======================== ###
    def create_new_component(self, parent_component_name: str="comp1", component_name: str="comp2") -> str:
        """
            {
                "name": "create_new_component",
                "description": "Creates a new component inside a specified parent component in Fusion 360. The parent component is identified by its name. If the parent component name matches the root component of the design, the new component is created in the root component.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "parent_component_name": {
                            "type": "string",
                            "description": "The name of the parent component where the new component will be created."
                        },
                        "component_name": {
                            "type": "string",
                            "description": "The name to be assigned to the new component."
                        }
                    },
                    "required": ["parent_component_name", "component_name"],
                    "returns": {
                        "type": "string",
                        "description": "Name of successfully created new component"
                    }

                }
            }
        """
        try:
            # Access the active design
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            rootComp = design.rootComponent

            # Determine the parent component
            if parent_component_name == rootComp.name:
                parentComponent = rootComp
            else:
                parentComponent = None
                for occ in rootComp.allOccurrences:
                    if occ.component.name == parent_component_name:
                        parentComponent = occ.component
                        break
                if not parentComponent:
                    error_msg = f'Parent component "{parent_component_name}" not found'
                    return error_msg

            # Create a new component
            newOccurrence = parentComponent.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            newComponent = newOccurrence.component
            newComponent.name = component_name

            return newComponent.name

        except Exception as e:
            error_msg = 'Failed to create new component:\n{}'.format(parent_component_name)
            return error_msg


    def set_parameter_value(self, parameter_name: str, new_value: float) -> str:
        """
        {
          "name": "set_parameter_value",
          "description": "Sets the value of a specified parameter in the active Fusion 360 design to a new numeric value. If the parameter doesn't exist or is read-only, an error is returned. Otherwise, a success message is returned.",
          "parameters": {
            "type": "object",
            "properties": {
              "parameter_name": {
                "type": "string",
                "description": "The name of the parameter to update."
              },
              "new_value": {
                "type": "number",
                "description": "The new numeric value to set."
              }
            },
            "required": ["parameter_name", "new_value"],
            "returns": {
              "type": "string",
              "description": "A message indicating whether the parameter was successfully updated."
            }
          }
        }
        """
        try:
            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)

            # Attempt to find the parameter by name
            param = design.allParameters.itemByName(parameter_name)
            if not param:
                return f"Error: Parameter '{parameter_name}' not found."

            # Attempt to set the new value
            # For user parameters, you can directly assign to 'value'.
            # For model parameters, you can also try param.expression = "..."
            # if direct value assignment isn't allowed.
            try:
                param.value = new_value
            except:
                # Some parameters may be read-only or locked, in which case
                # you might try setting the expression instead.
                try:
                    # Construct an expression by combining new_value with the parameter's unit
                    # (assuming the unit is valid for expressions).
                    if param.unit:
                        param.expression = f"{new_value} {param.unit}"
                    else:
                        param.expression = str(new_value)
                except:
                    return f"Error: Failed to update parameter '{parameter_name}'."

            return f"Parameter '{parameter_name}' successfully updated to {new_value}."

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    ### ================== IMPORT ============================ ###
    def import_fusion_component(self, parent_component_name: str, file_path: str) -> str:
        """
            {
              "name": "import_fusion_component",
              "description": "Imports a FusionArchive file into a specified parent component within the current Fusion 360 design.",
              "parameters": {
                "type": "object",
                "properties": {
                  "parent_component_name": {
                    "type": "string",
                    "description": "The name of the parent component in the current design where the FusionArchive file will be imported."
                  },
                  "file_path": {
                    "type": "string",
                    "description": "The local file path to the FusionArchive file to be imported."
                  }
                },
                "required": ["parent_component_name", "file_path"],
                "returns": {
                  "type": "string",
                  "description": "A message indicating the success or failure of the import operation."
                }
              }
            }
        """
        try:
            # Access the active design
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            rootComp = design.rootComponent

            # use base class method
            parentComponent = self._find_component_by_name(parent_component_name)
            if not targetComponent:
                return f'Parent component "{parent_component_name}" not found'

            # Access the import manager and create import options
            importManager = app.importManager
            fusionArchiveOptions = importManager.createFusionArchiveImportOptions(file_path)

            # Import the FusionArchive file into the parent component
            importManager.importToTarget(fusionArchiveOptions, parentComponent)

            return f'FusionArchive file imported into component "{parent_component_name}"'

        except Exception as e:
            return f'Failed to import FusionArchive file: {e}'

    def import_dxf_to_component(self, target_component : str, dxf_file_path: str):
        """
            {
              "name": "import_dxf_to_component",
              "description": "Imports a DXF file into a specified target component on its XY plane in Fusion 360. The function renames the new sketch to match the name of the DXF file, excluding the file extension.",

              "parameters": {
                "type": "object",
                "properties": {
                  "target_component": {
                    "type": "string",
                    "description": "The target component in Fusion 360 where the DXF file will be imported."
                  },
                  "dxf_file_path": {
                    "type": "string",
                    "description": "The file path of the DXF file to be imported."
                  }
                },
                "required": ["target_component", "dxf_file_path"]
              }
            }
        """

        newSketch = None
        try:
            # Check if target_component is a valid Fusion 360 Component object
            if not isinstance(self, target_component, adsk.fusion.Component):
                raise ValueError("target_component must be a fusion 360 Component object")

            app = adsk.core.Application.get()

            # Access the import manager
            importManager = app.importManager

            # Get the XY plane of the target component
            xyPlane = target_component.xYConstructionPlane

            # Create DXF import options
            dxfOptions = importManager.createDXF2DImportOptions(dxf_file_path, xyPlane)

            # Import the DXF file into the target component
            importManager.importToTarget(dxfOptions, target_component)

            # Extract the file name without extension
            file_name = os.path.splitext(os.path.basename(dxf_file_path))[0]

            # Find the newly created sketch by default name "0" and rename it
            for sketch in target_component.sketches:
                if sketch.name == "0":
                    sketch.name = file_name
                    newSketch = sketch
                    break

        except:
            if ui:
                ui.messageBox('Failed to import DXF file:\n{}'.format(traceback.format_exc()))


        return newSketch



    ### ================= MODIFY OBJECTS ===================== ###
    def rename_model_parameter(self, old_name: str, new_name: str) -> str:
        """
            {
              "name": "rename_model_parameter",
              "description": "Renames a model parameter in the active Fusion 360 design from old_name to new_name. Model parameters are typically associated with features and construction geometry. If the parameter does not exist or cannot be renamed, an error message is returned.",
              "parameters": {
                "type": "object",
                "properties": {
                  "old_name": {
                    "type": "string",
                    "description": "The existing name of the model parameter to rename."
                  },
                  "new_name": {
                    "type": "string",
                    "description": "The new name you want to give to the model parameter."
                  }
                },
                "required": ["old_name", "new_name"],
                "returns": {
                  "type": "string",
                  "description": "A message indicating whether the parameter was successfully renamed."
                }
              }
            }
        """
        try:
            app = adsk.core.Application.get()
            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)

            # Retrieve the parameter by its old name
            param = design.allParameters.itemByName(old_name)
            if not param:
                return f"Error: Parameter '{old_name}' not found."

            # Attempt to rename it
            try:
                param.name = new_name
            except Exception as rename_error:
                return f"Error: Failed to rename parameter '{old_name}' to '{new_name}'. Reason: {rename_error}"

            return f"Parameter '{old_name}' renamed to '{new_name}'."

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    def rename_model_parameters(self, old_new_names: list) -> str:
        """
            {
              "name": "rename_model_parameters",
              "description": "Renames multiple model parameters in the active Fusion 360 design. Accepts an array of objects, each containing an old_name and a new_name. Returns a summary indicating which renames succeeded or failed.",
              "parameters": {
                "type": "object",
                "properties": {
                  "old_new_names": {
                    "type": "array",
                    "items": {
                      "type": "object",
                      "properties": {
                        "old_name": {
                          "type": "string",
                          "description": "The current name of the model parameter."
                        },
                        "new_name": {
                          "type": "string",
                          "description": "The new name you wish to assign to the model parameter."
                        }
                      },
                      "required": ["old_name", "new_name"]
                    },
                    "description": "An array of old_name / new_name pairs for the parameters you want to rename."
                  }
                },
                "required": ["old_new_names"],
                "returns": {
                  "type": "string",
                  "description": "A summary message indicating the success or failure of each parameter rename."
                }
              }
            }
        """
        try:
            app = adsk.core.Application.get()

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)

            results = []  # To store individual success/error messages

            for pair in old_new_names:
                old_name = pair.get("old_name", "")
                new_name = pair.get("new_name", "")

                if not old_name or not new_name:
                    results.append(f"Skipping rename: Missing old_name or new_name in {pair}.")
                    continue

                # Retrieve the parameter by old_name
                param = design.allParameters.itemByName(old_name)
                if not param:
                    results.append(f"Error: Parameter '{old_name}' not found.")
                    continue

                # Attempt to rename
                try:
                    param.name = new_name
                    results.append(f"Renamed '{old_name}' to '{new_name}'.")
                except Exception as rename_error:
                    results.append(
                        f"Error: Failed to rename '{old_name}' to '{new_name}'. Reason: {rename_error}"
                    )

            # Combine all messages into a single result string
            summary = "\n".join(results)
            return summary

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()




    def rename_component(self, component_name: str, new_name: str) -> str:
        """
            {
              "name": "rename_component",
              "parameters": {
                "type": "object",
                "properties": {
                  "component_name": {
                    "type": "string",
                    "description": "The name of the Fusion 360 component to be renamed."
                  },
                  "new_name": {
                    "type": "string",
                    "description": "The new name to assign to the component."
                  }
                },
                "required": [
                  "component",
                  "new_name"
                ]
              },
              "description": "Renames a specified component in Fusion 360 to a new name."
            }
        """

        try:
            targetComponent = self._find_component_by_name(component_name)
            # Set the new name for the component
            targetComponent.name = new_name
            return new_name
        except Exception as e:
            return 'Failed to rename the component:\n{}'.format(new_name)


    def delete_component(self, component_name: str="comp1") -> str:
        """
        {
            "name": "delete_component",
            "description": "Deletes a component from the current Fusion 360 design based on the given component name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "component_name": {
                        "type": "string",
                        "description": "The name of the Fusion 360 component object to be deleted."
                    }
                },
                "required": ["component_name"]
            }
        }
        """
        try:

            targetComponent = self._find_component_by_name(component_name)
            if not targetComponent:
                return f'Error: Component "{component_name}" not found.'

            # Delete the component
            targetComponent.deleteMe()

            return f'deleted {component_name}'

        except Exception as e:
            return 'Failed to delete the component:\n{}'.format(component_name)

    def delete_sketch(self, component_name: str="comp1", sketch_name: str="sketch1") -> str:
        """
        {
            "name": "delete_sketch",
            "description": "Deletes a sketch from the current Fusion 360 design based on the given component and sketch names.",
            "parameters": {
                "type": "object",
                "properties": {
                    "component_name": {
                        "type": "string",
                        "description": "The name of the Fusion 360 component containing the sketch."
                    },
                    "sketch_name": {
                        "type": "string",
                        "description": "The name of the sketch to be deleted."
                    }
                },
                "required": ["component_name", "sketch_name"]
            }
        }
        """
        try:

            # Find the target component by name (assuming you have a helper method).
            targetComponent = self._find_component_by_name(component_name)
            if not targetComponent:
                return f'Error: Component "{component_name}" not found.'

            # Find the target sketch by name in the component.
            targetSketch = self._find_sketch_by_name(targetComponent)
            if not targetSketch:
                return f'Error: Sketch "{sketch_name}" not found in component "{component_name}".'

            # Delete the sketch.
            targetSketch.deleteMe()

            return f'Deleted sketch "{sketch_name}" from component "{component_name}".'

        except Exception as e:
            return f'Failed to delete the sketch "{sketch_name}" from "{component_name}":\n{e}'
    def delete_brep_body(self, component_name: str="comp1", body_name: str="body1") -> str:
        """
        {
            "name": "delete_brep_body",
            "description": "Deletes a BRep body from the current Fusion 360 design based on the given component name and body name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "component_name": {
                        "type": "string",
                        "description": "The name of the Fusion 360 component containing the BRep body."
                    },
                    "body_name": {
                        "type": "string",
                        "description": "The name of the BRep body to be deleted."
                    }
                },
                "required": ["component_name", "body_name"]
            }
        }
        """
        try:

            # Find the target component by name
            targetComponent = self._find_component_by_name(component_name)
            if not targetComponent:
                return f'Error: Component "{component_name}" not found.'

            # Search for the specified BRep body within the component
            targetBody = None
            for body in targetComponent.bRepBodies:
                if body.name == body_name:
                    targetBody = body
                    break

            if not targetBody:
                return f'Error: BRep body "{body_name}" not found in component "{component_name}".'

            # Delete the BRep body
            targetBody.deleteMe()

            return f'Deleted BRep body "{body_name}" from component "{component_name}".'

        except Exception as e:
            return f'Failed to delete the BRep body "{body_name}" from "{component_name}":\n{e}'

    def copy_component(self, source_component_name: str, target_parent_component_name: str) -> str:
        """
            {
                "name": "copy_component",
                "description": "Creates a new occurrence of an existing component inside another parent component. This effectively 'copies' the geometry by referencing the same underlying component in a new location.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source_component_name": {
                            "type": "string",
                            "description": "The name of the existing Fusion 360 component to be copied."
                        },
                        "target_parent_component_name": {
                            "type": "string",
                            "description": "The name of the component that will serve as the parent for the new copy."
                        }
                    },
                    "required": ["source_component_name", "target_parent_component_name"],
                    "returns": {
                        "type": "string",
                        "description": "A message indicating whether the copy (new occurrence) was successfully created."
                    }

                }
            }
        """
        try:
            # Access the active design
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return "Error: No active Fusion 360 design found."

            # Locate the source component using a helper method (assumed to exist in your environment)
            sourceComp = self._find_component_by_name(source_component_name)
            if not sourceComp:
                return f'Error: Source component "{source_component_name}" not found.'

            # Locate the target parent component
            targetParentComp = self._find_component_by_name(target_parent_component_name)
            if not targetParentComp:
                return f'Error: Parent component "{target_parent_component_name}" not found.'

            # Create a new occurrence of the source component in the target parent component
            transform = adsk.core.Matrix3D.create()  # Identity transform (no rotation, no translation)
            new_occurrence = targetParentComp.occurrences.addExistingComponent(sourceComp, transform)

            # (Optional) Rename the new occurrence if you want a distinct name
            # new_occurrence.name = source_component_name + "_copy"

            return f'Successfully copied "{source_component_name}" into "{target_parent_component_name}".'

        except Exception as e:
            return f'Failed to copy "{source_component_name}" into "{target_parent_component_name}":\n{e}'


    def copy_component_as_new(self, source_component_name: str="comp1", target_parent_component_name: str="comp_container", new_component_name: str="new_comp_1") -> str:
        """
            {
                "name": "copy_component_as_new",
                "description": "Creates a completely new component by copying the geometry of an existing component. The copied component is inserted as a new occurrence in the target parent component, but is otherwise independent of the source. The newly created component will be renamed to the provided new_component_name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source_component_name": {
                            "type": "string",
                            "description": "The name of the existing Fusion 360 component to be copied."
                        },
                        "target_parent_component_name": {
                            "type": "string",
                            "description": "The name of the component that will serve as the parent for the newly copied component."
                        },
                        "new_component_name": {
                            "type": "string",
                            "description": "The desired name for the newly created component copy."
                        }
                    },
                    "required": ["source_component_name", "target_parent_component_name", "new_component_name"],
                    "returns": {
                        "type": "string",
                        "description": "A message indicating whether the independent copy was successfully created and named."
                    }
                }
            }
        """
        try:
            # Access the active design
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return "Error: No active Fusion 360 design found."

            # Locate the source component
            sourceComp = self._find_component_by_name(source_component_name)
            if not sourceComp:
                return f'Error: Source component "{source_component_name}" not found.'

            # Locate the target parent component
            targetParentComp = self._find_component_by_name(target_parent_component_name)
            if not targetParentComp:
                return f'Error: Parent component "{target_parent_component_name}" not found.'

            # Create a new, independent copy of the source component
            transform = adsk.core.Matrix3D.create()  # Identity transform
            new_occurrence = targetParentComp.occurrences.addNewComponentCopy(sourceComp, transform)
            new_comp = new_occurrence.component

            # Rename the newly created component
            new_comp.name = new_component_name

            return f'Successfully created a new, independent copy of "{source_component_name}into "{target_parent_component_name}" named "{new_component_name}".'

        except Exception as e:
            return f'Failed to copy "{source_component_name}" as a new component into "{target_parent_component_name}":\n{e}'






















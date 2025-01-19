import adsk.core
import adsk.fusion
import traceback
import sys
import math
import os
import json

from multiprocessing.connection import Client
from array import array
import time

from ... import config

from ...lib import fusion360utils as futil


def print(string):
    """redefine print for fusion env"""
    futil.log(str(string))


class GptClient:
    """
    connects to command server runnin on seperate process
    """

    def __init__(self, fusion_interface):
        """
        fusion_interface : class inst whose methods call Fusion API
        """
        self.fusion_interface = fusion_interface 

        self.connect()
        time.sleep(1)

        #print(f"opening connection")
        #print(f"Connection Opened")


    def call_function(self, name, function_args):
        """
        call function passed from Assistants API
        """
        args = {}
        if function_args != None:
            func_args = json.loads(function_args)

        print(f"CALL FUNCTION: {name}, {func_args}")

        # check of FusionInterface inst has requested method
        function = getattr(self.fusion_interface, name, None )

        if callable(function):
            result = function(**func_args)
        else:
            result = ""

        return result


    def connect(self):
        """connect to assistant manager class on seperate process"""
        address = ('localhost', 6000)
        self.conn = Client(address, authkey=b'fusion260')


    def send_message(self, message):
        """send message"""


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

        return api_result


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



class FusionInterface():
    """
    interface between Fusion360 api and OpenAI Assistant
    methonds in this class are made avilable to the OpenAI Assistants API
    via the GptClient class
    """

    def __init__(self, app, ui):
        self.app = app
        self.ui = ui
        self.design = adsk.fusion.Design.cast(self.app.activeProduct)



    ### =================== GET OBJECTS ======================== ###
    def get_root_component_name(self):
        """
        {
            "name": "get_root_component_name",
            "description": "Retrieves the name of the root component in the current Fusion 360 design.",
            "parameters": {},
            "returns": {
              "type": "string",
              "description": "The name of the root component in the current design."
            }
        }
        """

        try:
            # Access the active design
            if self.design:
                # Return the name of the root component
                return self.design.rootComponent.name
            else:
                self.ui.messageBox('No active design found.')
                return None

        except Exception as e:
            self.ui.messageBox('Failed:\n{}'.format(e))
            return None


    def find_component_by_name(self, function_name):
        """
        {
          "name": "find_component_by_name",
          "description": "Searches for a component in the active Fusion 360 design. The function_name can be a single name or a hierarchical path represented by names separated by colons, indicating a path from a parent component to a nested child component.",

          "parameters": {
            "type": "object",
            "properties": {
              "function_name": {
                "type": "string",
                "description": "The name or hierarchical path of the component to search for, with names separated by colons if applicable."
              }
            },
            "required": ["function_name"]
          }
        }
        """
        try:
            # Get the active design
            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)

            if not design:
                ui.messageBox('No active Fusion 360 design', 'No Design')
                return None

            # Split the function_name on colons to get the component hierarchy
            component_names = function_name.split(':')

            # Start with the root component
            current_component = design.rootComponent

            # Iterate through the hierarchy
            for name in component_names:
                found = False
                for occ in current_component.allOccurrences:
                    if occ.component.name == name:
                        current_component = occ.component
                        found = True
                        break
                if not found:
                    return None  # Component in the hierarchy not found

            return current_component

        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
            return None



    ### =================== CREEATE OBJECTS ======================== ###
    def create_new_component(self, parent_component_name, component_name):
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
              "required": ["parent_component_name", "component_name"]
            }
        }
        """
        try:
            # Access the active design
            app = adsk.core.Application.get()
            ui = app.userInterface
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



    def create_sketch(self, component_name, sketch_name, sketch_plane="xy"):
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

            # Find the target component
            targetComponent = None
            for occ in rootComp.allOccurrences:
                if occ.component.name == component_name:
                    targetComponent = occ.component
                    break

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


    ### ================== IMPORT ============================ ###

    def import_fusion_component(self, parent_component_name, file_path):
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
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)
            rootComp = design.rootComponent

            # Find the target parent component
            parentComponent = None
            for occ in rootComp.allOccurrences:
                if occ.component.name == parent_component_name:
                    parentComponent = occ.component
                    break

            if not parentComponent:
                return f'Parent component "{parent_component_name}" not found'

            # Access the import manager and create import options
            importManager = app.importManager
            fusionArchiveOptions = importManager.createFusionArchiveImportOptions(file_path)

            # Import the FusionArchive file into the parent component
            importManager.importToTarget(fusionArchiveOptions, parentComponent)

            return f'FusionArchive file imported into component "{parent_component_name}"'

        except Exception as e:
            return f'Failed to import FusionArchive file: {e}'


    def import_dxf_to_component(self, target_component, dxf_file_path):
        """
        {
          "name": "import_dxf_to_component",
          "description": "Imports a DXF file into a specified target component on its XY plane in Fusion 360. The function renames the new sketch to match the name of the DXF file, excluding the file extension.",

          "parameters": {
            "type": "object",
            "properties": {
              "target_component": {
                "type": "adsk.fusion.Component",
                "description": "The target component in Fusion 360 where the DXF file will be imported."
              },
              "dxf_file_path": {
                "type": "str",
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



    ### ================== SKETCHES ===================== ###


    def create_circles_in_sketch(self, component_name, sketch_name, point_list, circle_diameter_list):
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

            # Find and delete the target component
            targetComponent = None
            for occ in rootComp.allOccurrences:
                if occ.component.name == component_name:
                    targetComponent = occ.component
                    break

            if not targetComponent:
                return f'Component "{component_name}" not found'

            # Find the target sketch
            targetSketch = None
            for sketch in targetComponent.sketches:
                if sketch.name == sketch_name:
                    targetSketch = sketch
                    break

            if not targetSketch:
                return f'Sketch "{sketch_name}" not found in component "{component_name}"'

            # Create circles in the sketch
            for point, diameter in zip(point_list, circle_diameter_list):
                centerPoint = adsk.core.Point3D.create(point[0], point[1], point[2])
                targetSketch.sketchCurves.sketchCircles.addByCenterRadius(centerPoint, diameter / 2)

            return f'Circles created in sketch "{sketch_name}"'

        except Exception as e:
            return f'Failed to create circles in sketch: {e}'


    def extrude_largest_profile(self, component_name, sketch_name, extrusion_distance):
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
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)
            rootComp = design.rootComponent

            # Find the target component
            targetComponent = None
            for occ in rootComp.allOccurrences:
                if occ.component.name == component_name:
                    targetComponent = occ.component
                    break

            if not targetComponent:
                return f'Component "{component_name}" not found'

            # Find the target sketch
            targetSketch = None
            for sketch in targetComponent.sketches:
                if sketch.name == sketch_name:
                    targetSketch = sketch
                    break

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


    def create_polygon_in_sketch(self, parent_component_name, sketch_name, point_list):
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



    ### ================= MODIFY OBJECTS ===================== ###

    def move_component_to_point(self, component_name, new_point):
        """
        {
          "name": "move_component_to_point",
          "description": "Moves an occurrence of a specified component to a new point within the Fusion 360 design. The function tries to capture the design's position after moving the component occurrence.",
          "parameters": {
            "type": "object",
            "properties": {
              "component_name": {
                "type": "string",
                "description": "The name of the component whose occurrence is to be moved."
              },
              "new_point": {
                "type": "array",
                "items": {
                  "type": "number"
                },
                "minItems": 3,
                "maxItems": 3,
                "description": "The new XYZ point (x, y, z) to move the component occurrence to."
              }
            },
            "required": ["component_name", "new_point"],
            "returns": {
              "type": "string",
              "description": "A message indicating the success or failure of the component occurrence movement."
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

            # Find the target component occurrence
            targetOccurrence = None
            for occ in rootComp.allOccurrences:
                if occ.component.name == component_name:
                    targetOccurrence = occ
                    break

            if not targetOccurrence:
                return f'Component occurrence for "{component_name}" not found'

            # Create a transform to move the occurrence
            transform = adsk.core.Matrix3D.create()
            transform.translation = adsk.core.Vector3D.create(new_point[0], new_point[1], new_point[2])
            targetOccurrence.transform = transform

            # Capture the design's position
            design.snapshots.add()

            return f'Occurrence of component "{component_name}" moved to point {new_point}'

        except Exception as e:
            return f'Failed to move component occurrence: {e}'



    def rename_component(self, component, new_name):
        """
        {
          "name": "rename_component",
          "parameters": {
            "type": "object",
            "properties": {
              "component": {
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
            # Set the new name for the component
            component.name = new_name
            return new_name

        except Exception as e:
            return 'Failed to rename the component:\n{}'.format(new_name)


    def delete_component(self, component_name):
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
            # Access the active design
            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)
            rootComp = design.rootComponent

            # Find and delete the target component
            targetComponent = None
            for occ in rootComp.allOccurrences:
                if occ.component.name == component_name:
                    targetComponent = occ
                    break

            if not targetComponent:
                ui.messageBox(f'Component "{component_name}" not found')
                return

            # Delete the component
            targetComponent.deleteMe()

            return f'deleted {component_name}'

        except Exception as e:
            return 'Failed to delete the component:\n{}'.format(component_name)


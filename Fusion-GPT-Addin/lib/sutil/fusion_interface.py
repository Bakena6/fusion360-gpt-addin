import adsk.core
import adsk.fusion
#import adsk.cam
import traceback
import sys
import math
import os
import json
import inspect
import re
#from multiprocessing.connection import Client
from array import array
import time

import importlib
import functools


from ... import config
from ...lib import fusion360utils as futil
from .shared import ToolCollection

from . import shared
from . import document_data
from . import cad_modeling


def print(string):
    """redefine print for fusion env"""
    futil.log(str(string))

print(f"RELOADED: {__name__.split("%2F")[-1]}")



# send info to html palette
PALETTE_ID = config.palette_id
app = adsk.core.Application.get()
ui = app.userInterface
palette = ui.palettes.itemById(PALETTE_ID)


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
        self.submodules = [
            document_data.GetStateData(),
            document_data.SetStateData(),
            cad_modeling.Sketches(),
            cad_modeling.CreateObjects(),
            ModifyObjects(),
            #DeleteObjects(),
            ImportExport(),
            Joints(),
            Timeline(),
    #        NonCad(),
        ]


        fusion_methods = {}
        for submod in self.submodules:
            for method_name, method in submod.methods.items():
                # add method from container classes to main interface class
                setattr(self, method_name, method)


    # TODO do this without hard coading modules name
    def _reload_modules(self):
        importlib.reload(shared)
        importlib.reload(document_data)
        importlib.reload(cad_modeling)


    def update_settings(self, settings_dict ):
        ToolCollection.update(settings_dict)



    def get_tools(self):
        """
        creates list fusion interface functions
        """
        methods = {}

        # add modules and create methods
        for mod in self.submodules:
            class_name = mod.__class__.__name__

            # class name used for display
            methods[class_name] = {}

            for attr_name in dir(mod):

                attr = getattr(mod, attr_name)
                wrapper = getattr(attr, "__wrapper__", None )
                if wrapper != "tool_call":
                    continue

                if str(attr.__class__) == "<class 'method'>":
                    # method signature
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

                    methods[class_name][attr_name] = param_dict

        return methods



    def get_docstr(self):
        """
        creates list fusion interface functions
        """
        method_list = []
        for attr_name in dir(self):

            attr = getattr(self, attr_name)

            if callable(attr) == False:
                continue

            if str(attr.__class__) == "<class 'method'>":
                sig = inspect.signature(attr)

                wrapper = getattr(attr, "__wrapper__", None )

                if wrapper != "tool_call":
                    continue

                docstring = attr.__doc__

                print(attr_name)
                json_method = json.loads(docstring)

                method_list.append(json_method)


        method_list = json.dumps(method_list)
        self.tools_json = method_list
        return method_list


    # TODO function calls should be wrapped
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
            print("func end")
            return result

        return wrapper




class NonCad(ToolCollection):


    def _set_appearance_on_occurrences(
        self, appearance_updates: list = [{"occurrence_name": "comp1:1","appearance_name":"Paint - Enamel Glossy (Green)"}]) -> str:

        """
            {
              "name": "set_appearance_on_occurrences",
              "description": "Sets the appearance on a list of occurrence. Each item in appearance_updates is {'occurrence_name': <occurrence_name>, 'appearance_name': <appearance_name>}.",
              "parameters": {
                "type": "object",
                "properties": {
                  "appearance_updates": {
                    "type": "array",
                    "description": "An array of objects with the form {'occurrence_name': <occurrence_name>, 'appearance_name': <appearance_name>}.",
                    "items": {
                      "type": "object",
                      "properties": {
                        "component_name": {
                          "type": "string"
                        },
                        "appearance_name": {
                          "type": "string"
                        }
                      },
                      "required": ["occurrence_name", "appearance_name"]
                    }
                  }
                },
                "required": ["appearance_updates"],
                "returns": {
                  "type": "string",
                  "description": "A summary message about which occurrence were updated or any errors encountered."
                }
              }
            }
        """

    
        try:
            if not appearance_updates or not isinstance(appearance_updates, list):
                return "Error: Must provide an array of updates in the form [{'occurrence_name': '...', 'appearance_name': '...'}, ...]."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)
            root_comp = design.rootComponent

            # A helper function to find an appearance by name in the design
            # (Optionally search the appearance libraries if not found in design).
            def find_appearance_by_name(appearance_name: str):
                # 1) Check the design's local appearances
                local_appearance = design.appearances.itemByName(appearance_name)
                if local_appearance:
                    return local_appearance

                # 2) Optionally, check libraries if not found in local. Comment this out if not needed.
                appearance_libraries = app.materialLibraries
                for i in range(appearance_libraries.count):

                    a_lib = appearance_libraries.item(i)
                    if a_lib.name not in ["Fusion Appearance Library"]:
                        continue

                    lib_app = a_lib.appearances.itemByName(appearance_name)

                    if lib_app:
                        # You typically need to copy the library appearance into the design before applying
                        return design.appearances.addByCopy(lib_app, appearance_name)

                return None

            results = []
            # Process each update item
            for update in appearance_updates:
                # Validate each item in the array
                if not isinstance(update, dict):
                    results.append("Error: Appearance update must be a dictionary.")
                    continue

                occ_name = update.get("occurrence_name")
                app_name = update.get("appearance_name")

                if not occ_name or not app_name:
                    results.append(f"Error: Missing occurrence_name or appearance_name in {update}.")
                    print("contine")
                    continue

                # Find the appearance by name
                appearance = find_appearance_by_name(app_name)

                if not appearance:
                    results.append(f"Error: Appearance '{app_name}' not found in design or libraries.")
                    continue

                #  in case occurrences was passed in
                targetOcc, errors = self._find_occurrence_by_name(occ_name)
                print(f"targetOcc: {targetOcc}")
                if not targetOcc:
                    results.append(f"Error: Appearance '{app_name}' not found in design or libraries.")
                    continue

                # Setting the appearance property on an occurrence
                targetOcc.appearance = appearance
                # If needed, you can enforce override with:
                #targetOcc.appearance.isOverride = True
                results.append(f"Appearance set on occurrence: {occ_name}")


            return "\n".join(results)

        except:
            print("ERROR")
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()



    # TODO
    def capture_component_position(self, component_name: str = "comp1") -> str:
        """
        {
          "name": "capture_component_position",
          "description": "Retrieves the current global position (translation) of each occurrence referencing the specified component.",
          "parameters": {
            "type": "object",
            "properties": {
              "component_name": {
                "type": "string",
                "description": "The name of the Fusion 360 component whose occurrences' positions will be captured."
              }
            },
            "required": ["component_name"],
            "returns": {
              "type": "string",
              "description": "A JSON array where each element has an 'occurrenceName' and 'position' [x, y, z] in centimeters."
            }
          }
        }
        """

        return ""
        try:
            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)
            root_comp = design.rootComponent

            # Find all occurrences of this component
            target_occurrences = []
            for i in range(root_comp.occurrences.count):
                occ = root_comp.occurrences.item(i)
                if occ.component.name == component_name:
                    target_occurrences.append(occ)

            if not target_occurrences:
                return f"Error: No occurrences found for component '{component_name}'."

            # Collect the translation vector (x, y, z) for each occurrence
            positions_info = []
            for occ in target_occurrences:
                transform = occ.transform
                translation = transform.translation
                positions_info.append({
                    "occurrenceName": occ.name,
                    "position": [translation.x, translation.y, translation.z]
                })

            # Return the data as a JSON array string
            return json.dumps(positions_info)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()



class ModifyObjects(ToolCollection):

    #@ToolCollection.tool_call
    def _copy_component_as_new(self,
                       old_name: str = "M6-Socket-Head-Screw",
                       new_name: str = "CopiedComponent") -> str:
        """
        {
          "name": "copy_component_as_new",
          "description": "Creates a new copy of an existing component by copying an occurrence of the original, then pasting it as a new independent component with the specified new name.",
          "parameters": {
            "type": "object",
            "properties": {
              "old_name": {
                "type": "string",
                "description": "Name of the existing component to copy."
              },
              "new_name": {
                "type": "string",
                "description": "Name for the newly created component copy."
              }
            },
            "required": ["old_name", "new_name"],
            "returns": {
              "type": "string",
              "description": "A message indicating success or any error encountered."
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
            root_comp = design.rootComponent

            # Find an occurrence whose component name matches old_name
            source_occ = None
            all_occurrences = root_comp.allOccurrences
            for occ in all_occurrences:
                if occ.component.name == old_name:
                    source_occ = occ
                    break

            if not source_occ:
                return f"Error: No occurrence found for component '{old_name}'."

            # Build an ObjectCollection with this occurrence for copy/paste
            entities_to_copy = adsk.core.ObjectCollection.create()
            entities_to_copy.add(source_occ)

            # 1) Copy the occurrence
            design.copy(entities_to_copy)

            # 2) Paste as a new component definition
            pasted_objs = design.pasteNew()
            if not pasted_objs or pasted_objs.count < 1:
                return "Error: pasteNew() failed to create a new component."

            # Typically, the pasted_objs should contain one new occurrence referencing a new component
            new_occ = pasted_objs.item(0)

            # Rename the new component
            new_occ.component.name = new_name

            return (f"Successfully created a copy of '{old_name}' as '{new_name}'. "
                    f"New occurrence name: {new_occ.name}")

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


    @ToolCollection.tool_call
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

            sourceComp, errors = self._find_component_by_name(source_component_name)
            if not sourceComp:
                return errors

            targetParentComp, errors = self._find_component_by_name(target_parent_component_name)
            if not targetParentComp:
                return errors

            # Create a new occurrence of the source component in the target parent component
            transform = adsk.core.Matrix3D.create()  # Identity transform (no rotation, no translation)
            new_occurrence = targetParentComp.occurrences.addExistingComponent(sourceComp, transform)

            # (Optional) Rename the new occurrence if you want a distinct name
            # new_occurrence.name = source_component_name + "_copy"

            return f'Successfully copied "{source_component_name}" into "{target_parent_component_name}".'

        except Exception as e:
            return f'Error: Failed to copy "{source_component_name}" into "{target_parent_component_name}":\n{e}'

    @ToolCollection.tool_call
    def fillet_or_chamfer_edges(self,
                               component_name: str = "comp1",
                               body_name: str = "Body1",
                               edge_index_list: list = [0],
                               operation_value: float = 0.2,
                               operation_type: str = "fillet") -> str:
        """
        {
          "name": "fillet_or_chamfer_edges",
          "description": "Applies either a fillet or chamfer to the specified edges of a body.",
          "parameters": {
            "type": "object",
            "properties": {
              "component_name": {
                "type": "string",
                "description": "Name of the Fusion 360 component containing the target body."
              },
              "body_name": {
                "type": "string",
                "description": "Name of the BRep body whose edges will be modified."
              },
              "edge_index_list": {
                "type": "array",
                "description": "A list of integer edge indexes from the body whose edges will be filleted or chamfered.",
                "items": {
                  "type": "number"
                }
              },
              "operation_value": {
                "type": "number",
                "description": "The distance (radius or chamfer distance) to apply, in centimeters."
              },
              "operation_type": {
                "type": "string",
                "description": "Either 'fillet' or 'chamfer'."
              }
            },
            "required": ["component_name", "body_name", "edge_index_list", "operation_value", "operation_type"],
            "returns": {
              "type": "string",
              "description": "A message indicating success or details about any errors encountered."
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


            # find the target component by name (assuming you have a local helper method).
            targetComponent, errors = self._find_component_by_name(component_name)
            if not targetComponent:
                return errors

            body, errors  = self._find_body_by_name(targetComponent, body_name)
            if not body:
                return errors

            # Validate operation_type
            op_type_lower = operation_type.lower()
            if op_type_lower not in ("fillet", "chamfer"):
                return f"Error: Invalid operation_type '{operation_type}'. Must be 'fillet' or 'chamfer'."

            # Collect edges
            edges = body.edges
            edge_collection = adsk.core.ObjectCollection.create()
            invalid_indexes = []
            for idx in edge_index_list:
                if 0 <= idx < edges.count:
                    edge_collection.add(edges[idx])
                else:
                    invalid_indexes.append(idx)

            # If no valid edges were found, return an error.
            if edge_collection.count == 0:
                return f"Error: No valid edges found. Invalid indexes: {invalid_indexes}" if invalid_indexes else "Error: No valid edges provided."

            # Create either a fillet or a chamfer
            if op_type_lower == "fillet":
                try:
                    fillet_feats = targetComponent.features.filletFeatures
                    fillet_input = fillet_feats.createInput()
                    # Construct the radius ValueInput
                    radius_val = adsk.core.ValueInput.createByReal(float(operation_value))
                    # Add all edges to a single radius set
                    fillet_input.addConstantRadiusEdgeSet(edge_collection, radius_val, True)
                    fillet_feats.add(fillet_input)
                    msg = f"Fillet applied with radius {operation_value} to edges: {edge_index_list}."
                except Exception as e:
                    return f"Error: Error creating fillet: {e}"
            else:  # chamfer
                try:
                    chamfer_feats = targetComponent.features.chamferFeatures
                    # For a simple equal-distance chamfer, we set 'distance'
                    distance_val = adsk.core.ValueInput.createByReal(float(operation_value))
                    # The createInput function signature is chamferFeatures.createInput(ObjectCollection, isTangentChain)
                    chamfer_input = chamfer_feats.createInput(edge_collection, True)
                    chamfer_input.setToEqualDistance(distance_val)
                    chamfer_feats.add(chamfer_input)
                    msg = f"Chamfer applied with distance {operation_value} to edges: {edge_index_list}."
                except Exception as e:
                    return f"Error: Error creating chamfer: {e}"

            # Include any invalid edge indexes in the output message for clarity
            if invalid_indexes:
                msg += f" Some invalid indexes were ignored: {invalid_indexes}"

            return msg

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def move_occurrence(self,
                       occurrence_name: str = "comp1:1",
                       move_position: list = [1.0, 1.0, 0.0]) -> str:
        """
        {
          "name": "move_occurrence",
          "description": "Moves the specified occurrence so that its local origin is placed at the given [x, y, z] point in centimeters.",
          "parameters": {
            "type": "object",
            "properties": {
              "occurrence_name": {
                "type": "string",
                "description": "Name of the Fusion 360 occurrence to move."
              },
              "move_position": {
                "type": "array",
                "description": "The [x, y, z] coordinates (in centimeters) to place the component's local origin in the global coordinate system.",
                "items": { "type": "number" }
              }
            },
            "required": ["occurrence_name", "move_position"],
            "returns": {
              "type": "string",
              "description": "A message indicating the result of the move operation."
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
            root_comp = design.rootComponent
            features = root_comp.features

            # Validate the move_position format: expecting [x, y, z].
            if (not isinstance(move_position, list)) or (len(move_position) < 3):
                return "Error: move_position must be an array of [x, y, z]."

            # Extract the coordinates (in centimeters)
            x_val, y_val, z_val = move_position

            targetOccurrence, errors = self._find_occurrence_by_name(occurrence_name)
            if not targetOccurrence:
                return errors

            # Create a transform with the translation [x_val, y_val, z_val].
            transform = adsk.core.Matrix3D.create()
            translation = adsk.core.Vector3D.create(x_val, y_val, z_val)
            transform.translation = translation

            try:
                targetOccurrence.timelineObject.rollTo(False)
                targetOccurrence.initialTransform = transform
                #occ.transform = transform

            except Exception as e:
                return f"Error: Could not transform occurrence '{occurrence_name}'. Reason: {e}"

            timeline = design.timeline
            timeline.moveToEnd()


            return (f"Moved occurrence '{occurrence_name}' to "
                    # TODO
                    f"[{x_val}, {y_val}, {z_val}] cm")

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def reorient_occurrence(self, occurrence_name: str = "comp1:1", axis: list = [0, 0, 1], target_vector: list = [1, 0, 0]) -> str:
        """
        {
          "name": "reorient_occurrence",
          "description": "Reorients the specified occurrence by rotating its local orientation so that a given axis is aligned with a specified target vector. Both the axis and target vector should be provided as arrays of three numbers representing 3D directions. The function uses Matrix3D.setToRotateTo to compute the necessary rotation transform.",
          "parameters": {
            "type": "object",
            "properties": {
              "occurrence_name": {
                "type": "string",
                "description": "Name of the Fusion 360 occurrence to reorient."
              },
              "axis": {
                "type": "array",
                "description": "A list of three numbers representing the current orientation axis (direction vector) of the occurrence that will be rotated.",
                "items": { "type": "number" },
                "minItems": 3,
                "maxItems": 3
              },
              "target_vector": {
                "type": "array",
                "description": "A list of three numbers representing the target direction for the specified axis.",
                "items": { "type": "number" },
                "minItems": 3,
                "maxItems": 3
              }
            },
            "required": ["occurrence_name", "axis", "target_vector"],
            "returns": {
              "type": "string",
              "description": "A message indicating the result of the reorientation operation."
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
            root_comp = design.rootComponent

            # Validate the axis and target_vector parameters: expecting lists of 3 numbers each.
            if not (isinstance(axis, list) and len(axis) == 3):
                return "Error: 'axis' must be a list of 3 numbers."
            if not (isinstance(target_vector, list) and len(target_vector) == 3):
                return "Error: 'target_vector' must be a list of 3 numbers."

            # Create Vector3D objects from the provided lists.
            fromVector = adsk.core.Vector3D.create(axis[0], axis[1], axis[2])
            toVector = adsk.core.Vector3D.create(target_vector[0], target_vector[1], target_vector[2])

            # Create a transformation matrix and set it to rotate from the 'fromVector' to the 'toVector'
            transform = adsk.core.Matrix3D.create()
            success = transform.setToRotateTo(fromVector, toVector)
            if not success:
                return "Error: Could not compute rotation transform using setToRotateTo."

            # Find the target occurrence using a helper method.
            targetOccurrence, errors = self._find_occurrence_by_name(occurrence_name)
            if not targetOccurrence:
                return f"Error: No occurrence found for '{occurrence_name}'."

            try:
                targetOccurrence.timelineObject.rollTo(False)
                targetOccurrence.initialTransform = transform
            except Exception as e:
                return f"Error: Could not reorient occurrence '{occurrence_name}'. Reason: {e}"

            timeline = design.timeline
            timeline.moveToEnd()

            return (f"Reoriented occurrence '{occurrence_name}' such that the axis {axis} is rotated "
                    f"to align with {target_vector}.")
        except Exception as e:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


    @ToolCollection.tool_call
    def mirror_body_in_component(
        self,
        component_name: str = "comp1",
        body_name: str = "Body1",
        operation_type: str = "JoinFeatureOperation",
        mirror_plane: str = "XY"
    ) -> str:
        """
        {
          "name": "mirror_body_in_component",
          "description": "Mirrors a specified body in a component along one of the component's planes (XY, XZ, YZ) or a planar face in the body by face index. It creates a MirrorFeature in the timeline.",
          "parameters": {
            "type": "object",
            "properties": {
              "component_name": {
                "type": "string",
                "description": "The name of the component containing the target body."
              },
              "body_name": {
                "type": "string",
                "description": "The name of the BRepBody to mirror."
              },
              "operation_type": {
                "type": "string",
                "description": "Either 'JoinFeatureOperation' or 'NewBodyFeatureOperation'.",
                "enum": [
                  "JoinFeatureOperation",
                  "NewBodyFeatureOperation"
                ]
              },
              "mirror_plane": {
                "type": "string",
                "description": "The plane to mirror about. Accepted values: 'XY', 'XZ', 'YZ' (the component's origin planes) OR a face reference in the form 'FaceIndex=3'."
              }
            },
            "required": ["component_name", "body_name", "operation_type", "mirror_plane"],
            "returns": {
              "type": "string",
              "description": "A message indicating success or any error encountered."
            }
          }
        }
        """

        try:
            # Validate operation_type
            valid_ops = ["JoinFeatureOperation", "NewBodyFeatureOperation"]
            if operation_type not in valid_ops:
                return (f"Error: operation_type '{operation_type}' must be one of: {valid_ops}.")

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)


            # Find the target component by name (assuming you have a helper method).
            targetComponent, errors = self._find_component_by_name(component_name)
            if not targetComponent:
                return errors

            body_to_mirror, errors  = self._find_body_by_name(targetComponent, body_name)
            if not body_to_mirror:
                return errors

            # Decide on the mirror plane
            mirror_plane_obj = None

            # 1) If it's one of 'XY', 'XZ', or 'YZ', use the component's origin planes
            plane_label = mirror_plane.upper().strip()
            if plane_label in ["XY", "XZ", "YZ"]:
                planes = targetComponent.constructionPlanes

                #TODO
                #origin_planes = target_comp.originConstructionPlanes
                # originConstructionPlanes has .item(0)=XY, .item(1)=XZ, .item(2)=YZ in typical order
                # But let's map them carefully:
                plane_map = {
                    "XY": targetComponent.xYConstructionPlane,
                    "XZ": targetComponent.xZConstructionPlane,
                    "YZ": targetComponent.yZConstructionPlane,
                }
                mirror_plane_obj = plane_map.get(plane_label)

            # 2) If it starts with 'FaceIndex=', interpret it as a face index on the body
            elif plane_label.startswith("FACEINDEX="):
                # Parse out the integer
                try:
                    face_index = int(plane_label.split("=")[1])
                except:
                    return f"Error: Could not parse face index from '{mirror_plane}'."
                if face_index < 0 or face_index >= body_to_mirror.faces.count:
                    return f"Error: Face index {face_index} out of range for body '{body_name}'."
                face_obj = body_to_mirror.faces.item(face_index)
                # The face must be planar
                plane_face = adsk.fusion.BRepFace.cast(face_obj)
                if not plane_face or not plane_face.geometry or not isinstance(plane_face.geometry, adsk.core.Plane):
                    return f"Error: Face {face_index} is not planar, cannot mirror about it."
                mirror_plane_obj = plane_face

            else:
                return (f"Error: mirror_plane '{mirror_plane}' is invalid. "
                        "Use 'XY', 'XZ', 'YZ', or 'FaceIndex=N' with a planar face.")

            if not mirror_plane_obj:
                return f"Error: Could not obtain a valid mirror plane from '{mirror_plane}'."

            # Build the input for the MirrorFeature
            mirror_feats = targetComponent.features.mirrorFeatures
            input_entities = adsk.core.ObjectCollection.create()
            input_entities.add(body_to_mirror)

            mirror_input = mirror_feats.createInput(input_entities, mirror_plane_obj)

            # If you want to specify Join vs NewBody, do so via isCombine for MirrorFeatures
            # https://help.autodesk.com/view/fusion360/ENU/?guid=Fusion360_API_Reference_manual_cpp_ref_classadsk_1_1fusion_1_1_mirror_feature_input_html
            if operation_type == "JoinFeatureOperation":
                mirror_input.isCombine = True
            else:
                mirror_input.isCombine = False

            try:
                mirror_feature = mirror_feats.add(mirror_input)
                return (f"Mirrored body '{body_name}' in component '{component_name}' about "
                        f"plane '{mirror_plane}' with operation '{operation_type}'.")
            except Exception as e:
                return f"Error creating mirror feature: {str(e)}"

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


class ImportExport(ToolCollection):

    @ToolCollection.tool_call
    def list_step_files_in_directory(self) -> str:
        """
        {
          "name": "list_step_files_in_directory",
          "description": "Recursively navigates a given directory and returns an organized JSON-like object containing the names and full file paths of all STEP files. STEP files are identified by the '.step' or '.stp' extension. The returned structure organizes the files by directory, listing files and nested subdirectories. The root directory path is hard coded by the user",
          "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "returns": {
              "type": "object",
              "description": "An organized JSON-like object with keys 'files' and 'subdirectories'. 'files' is a list of objects each containing 'name' and 'path' for STEP files in the current directory, while 'subdirectories' is a dictionary mapping each subdirectory name to its own similar object."
            }
          }
        }
        """

        try:

            def recursive_scan(current_path):
                # Initialize the result for the current directory
                result = {"files": [], "subdirectories": {}}
                with os.scandir(current_path) as it:
                    for entry in it:
                        if entry.is_file():
                            # Check if file extension is .step or .stp (case-insensitive)
                            if entry.name.lower().endswith(('.step', '.stp')):
                                result["files"].append({
                                    "name": entry.name,
                                    "path": os.path.abspath(entry.path)
                                })
                        elif entry.is_dir():
                            # Recursively scan subdirectories
                            result["subdirectories"][entry.name] = recursive_scan(entry.path)
                return result

            directory_path = config.LOCAL_CAD_PATH

            organized_result = recursive_scan(directory_path)

            return json.dumps(organized_result)

        except Exception as e:
            return f"Error: Failed to scan local directory: {e}"

    @ToolCollection.tool_call
    def import_step_file_to_component(self, target_component: str="comp1", file_path: str="paath"):
        """
        {
          "name": "import_step_file_to_component",
          "description": "Imports a STEP file into a specified target component in Fusion 360. The STEP file is read from the local file path and its geometry is inserted into the target component. This function uses the Fusion 360 import manager to create an import operation.",
          "parameters": {
            "type": "object",
            "properties": {
              "target_component": {
                "type": "string",
                "description": "The name of the target component in the current design where the STEP file will be imported."
              },
              "file_path": {
                "type": "string",
                "description": "The local file path of the STEP file to be imported."
              }
            },
            "required": ["target_component", "file_path"],
            "returns": {
              "type": "string",
              "description": "A message indicating the success or failure of the STEP file import."
            }
          }
        }
        """
        try:
            # Access the active Fusion 360 design
            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return "Error: No active Fusion 360 design found."

            # find the target component by name (assuming you have a local helper method).
            targetComp, errors = self._find_component_by_name(target_component)
            if not targetComp:
                return errors

            # Get the import manager from the application
            importMgr = app.importManager

            # Create the STEP import options with the provided file path and target component.
            # Note: The API method createSTEPImportOptions expects a file path and the target component.
            stepOptions = importMgr.createSTEPImportOptions(file_path)
            #prevent auto resize
            stepOptions.isViewFit = False

            # Execute the import operation into the target component
            importOperation = importMgr.importToTarget(stepOptions, targetComp)

            #camera_ = app.activeViewport.camera
            #camera_.isFitView = True
            #app.activeViewport.camera = camera_

            return f"STEP file imported successfully into component '{target_component}'."
        except Exception as e:
            return f"Error: Failed to import STEP file: {e}"

    @ToolCollection.tool_call
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
                ui.messageBox('Error: Failed to import DXF file:\n{}'.format(traceback.format_exc()))


        return newSketch

    @ToolCollection.tool_call
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

            parentComponent, errors = self._find_component_by_name(parent_component_name)
            if not parentComponent:
                return errors

            # Access the import manager and create import options
            importManager = app.importManager
            fusionArchiveOptions = importManager.createFusionArchiveImportOptions(file_path)

            # Import the FusionArchive file into the parent component
            importManager.importToTarget(fusionArchiveOptions, parentComponent)

            return f'FusionArchive file imported into component "{parent_component_name}"'

        except Exception as e:
            return f'Failed to import FusionArchive file: {e}'


class DeleteObjects(ToolCollection):

    #@ToolCollection.tool_call
    def delete_component_sub_object(self, delete_object_array :list=[
            {"component_name": "comp1", "object_type":"jointOrigins", "object_name":"Joint Origin1"},
            {"component_name": "comp1", "object_type":"jointOrigins", "object_name":"Joint Origin1"},
            {"component_name": "comp1", "object_type":"jointOrigins", "object_name":"Joint Origin1"},
    ]) -> str:

        """
        {
            "name": "delete_component_sub_object",
            "description": "Deletes any valid object inside of component",
            "parameters": {
                "type": "object",
                "properties": {

                    "delete_object_array": {
                        "type": "array",
                        "description": "Array of objects to delete",

                        "items": {
                            "type": "object",
                            "properties": {
                                "component_name": {
                                    "type": "string",
                                    "description": "name of the component containing the object to delete"
                                },
                                "object_type": {
                                    "type": "string",
                                    "description": "type of object to delete",
                                    "enum": [ "sketches",
                                            "bRepBodies",
                                            "meshBodies",
                                            "joints",
                                            "jointOrigins",
                                            "occurrences",
                                            "rigidGroups"]
                                },
                                "object_name": {
                                    "type": "string",
                                    "description": "The name of the object to delete"
                                }
                            },
                            "required": ["component_name", "object_type", "object_name"]
                        }

                    }
                },

                "required": ["delete_object_array"],
                "returns": {
                    "type": "string",
                    "description": "A message indicating success or failure of the deletions."
                }
            }
        }
        """
        try:
            # Access the active design.
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            rootComp = design.rootComponent

            # check arg type
            if not isinstance(delete_object_array, list):
                return "Error: delete_object_array must be an array/ list"

            delete_enums = [
                "sketches",
                "bRepBodies",
                "meshBodies",
                "joints",
                "jointOrigins",
                "occurrences",
                "rigidGroups",
            ]

            # add object to delete to dict, faster this way
            delete_dict = {}

            results = []
            # jonied as string and returned
            # items in array, each representing a delete task
            for delete_object in delete_object_array:
                component_name = delete_object.get("component_name")

                object_type = delete_object.get("object_type")
                object_name = delete_object.get("object_name")

                targetComponent, errors = self._find_component_by_name(component_name)

                if not targetComponent:
                    # if results, add error to return list
                    results.append(errors)
                    continue

                # comp.sketches, comp.bodies, comp.joints etc
                object_class = getattr(targetComponent, object_type, None)

                # check if delete object class list exists
                if object_class == None:
                    results.append(f"Error: Component {component_name} has not attribute '{object_type}'.")
                    continue

                # check that attr has 'itemByName' method before calling it
                if hasattr(object_class, "itemByName") == False:
                    errors = f"Error: Component {component_name}.{object_type} has no method 'itemByName'."
                    results.append(errors)
                    continue

                # select object to delete by name, sketch, body, joint, etc
                target_object = object_class.itemByName(object_name)

                # check if item by name is None
                if target_object == None:
                    errors = f"Error: Component {component_name}: {object_type} has no item {object_name}."
                    available_objects = [o.name for o in object_class]
                    errors += f" Available objects in {component_name}.{object_type}: {available_objects}"
                    results.append(errors)
                    continue

                # check if item can be delete
                if hasattr(target_object,"deleteMe") == False:
                    errors = f"Error: Component {component_name}.{object_type} object {object_name} has no attribute deleteMe."
                    results.append(errors)
                    continue


                delete_dict[f"{component_name}.{object_type}.{target_object.name}"] = target_object
                #results.append(f'Added {component_name}.{object_type} "{target_object.name}" to delete list.')


            if len(list(delete_dict.keys())) == 0:
                results.append(f"No objects to delete.")

            for k, v in delete_dict.items():
                delete_result = v.deleteMe()

                if delete_result == True:
                    results.append(f"Deleted {k}.")
                else:
                    results.append(f"Error deleting {k}.")


            #delete_name_list = []
            #deleteCollection = adsk.core.ObjectCollection.create()
            #for deleteObject in delete_list:
            #    deleteCollection.add(deleteObject)

            #design.deleteEntities(deleteCollection)
            #print(deleteCollection)

            #results.append("All object deleted")

            return "\n".join(results).strip()

        except:
            return f'Error: Failed to delete objects:\n{traceback.format_exc()}'


    #@ToolCollection.tool_call
    def delete_occurrence(self, occurrence_name: str="comp1:1") -> str:
        """
        {
            "name": "delete_occurrence",
            "description": "Deletes a occurrence from the current Fusion 360 design based on the given occurrence name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "occurrence_name": {
                        "type": "string",
                        "description": "The name of the Fusion 360 occurrence object to be deleted."
                    }
                },
                "required": ["occurrence_name"]
            }
        }
        """
        try:

            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            rootComp = design.rootComponent

            targetOccurrence, errors, = self._find_occurrence_by_name(occurrence_name)
            if not targetOccurrence:
                return errors

            targetOccurrence.deleteMe()

            return f'deleted {occurrence_name}'

        except Exception as e:
            return f'Error: Failed to delete occurrence "{occurrence_name}":\n{e}'


class Joints(ToolCollection):

    @ToolCollection.tool_call
    def list_joint_origin_references(self, component_name: str = "comp1") -> str:
        """
        {
          "name": "list_joint_origin_references",
          "description": "Finds potential reference geometry (faces, edges, vertices, sketch points) in the specified component that can host a Joint Origin. Returns a JSON array, each item includes geometry type, name or index, a referenceId, and approximate X/Y/Z coordinates.",
          "parameters": {
            "type": "object",
            "properties": {
              "component_name": {
                "type": "string",
                "description": "Name of the Fusion 360 component whose geometry references will be listed."
              }
            },
            "required": ["component_name"],
            "returns": {
              "type": "string",
              "description": "A JSON array of references. Each entry might look like { 'referenceId': 'face|body0|face3', 'geometryType': 'face', 'location': [x, y, z], ... }"
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

            # Find the target component by name
            targetComponent = None
            for comp in design.allComponents:
                if comp.name == component_name:
                    targetComponent = comp
                    break
            if not targetComponent:
                return f"Error: Component '{component_name}' not found."

            references_list = {
                "faces": [],
                "edges": [],
                "vertices": [],
                "sketch_points": [],

            }

            # A helper to get the bounding box center in [x, y, z].
            def bounding_box_center(bbox: adsk.core.BoundingBox3D):
                x = 0.5 * (bbox.minPoint.x + bbox.maxPoint.x)
                y = 0.5 * (bbox.minPoint.y + bbox.maxPoint.y)
                z = 0.5 * (bbox.minPoint.z + bbox.maxPoint.z)
                return [x, y, z]


            # 1) Collect faces (using bounding box center)
            for bodyIndex, body in enumerate(targetComponent.bRepBodies):
                for faceIndex, face in enumerate(body.faces):
                    refId = f"face|body{bodyIndex}|face{faceIndex}"
                    bbox = face.boundingBox
                    loc = bounding_box_center(bbox) if bbox else [0, 0, 0]

                    face_type = face.geometry.objectType
                    #face_type = face.geometry.surfaceType
                    #print(dir(face.geometry))
                    print(f"{faceIndex}: {face_type}")

                    references_list["faces"].append({
                        "referenceId": refId,
                        "geometryType": "face",
                        "faceType": face_type,
                        "number_of_edges": face.edges.count,
                        "area": face.area,
                        "bodyName": body.name,
                        "faceIndex": faceIndex,
                        "location": loc
                    })

            # 2) Collect edges (using bounding box center)
            for bodyIndex, body in enumerate(targetComponent.bRepBodies):
                for edgeIndex, edge in enumerate(body.edges):
                    refId = f"edge|body{bodyIndex}|edge{edgeIndex}"

                    geoType = ""
                    edgeGeo = edge.geometry
                    if isinstance(edgeGeo, adsk.core.Circle3D):
                        geoType = "Circle3D"
                        loc = edge.geometry.center.asArray()
                    elif isinstance(edgeGeo, adsk.core.Line3D):
                        geoType = "Line3D"
                        loc = edge.geometry.startPoint.asArray()
                    elif isinstance(edgeGeo, adsk.core.Arc3D):
                        geoType = "Arc3D"
                        loc = edge.geometry.center.asArray()
                    else:
                        print(edge.geometry)
                        loc = None

                    if geoType != "Circle3D":
                        continue

                    edgeDict = {
                        "referenceId": refId,
                        "geometryType": f"Edge",
                        "edgeType": geoType,
                        "bodyName": body.name,
                        "edgeIndex": edgeIndex,
                        "location": loc
                    }

                    if geoType == "Circle3D":
                        edgeDict["radius"] = edge.geometry.radius 

                    references_list["edges"].append(edgeDict)


            # 3) Collect vertices (bounding box center = actual vertex coords)
            for bodyIndex, body in enumerate(targetComponent.bRepBodies):
                for vertIndex, vertex in enumerate(body.vertices):
                    refId = f"vertex|body{bodyIndex}|vertex{vertIndex}"

                    if isinstance(vertex, adsk.fusion.BRepVertex):
                        loc = vertex.geometry.asArray()
                    else:
                        loc = None

                    #loc = bounding_box_center(bbox) if bbox else [0, 0, 0]
                    references_list["vertices"].append({
                        "referenceId": refId,
                        "geometryType": "vertex",
                        "bodyName": body.name,
                        "vertexIndex": vertIndex,
                        "location": loc
                    })

            # 4) Collect sketch points (use the 3D geometry of the point)
            for sketchIndex, sketch in enumerate(targetComponent.sketches):
                for pointIndex, skPoint in enumerate(sketch.sketchPoints):
                    refId = f"sketchPoint|sketch{sketchIndex}|point{pointIndex}"
                    geo = skPoint.worldGeometry  # a Point3D in global coords

                    loc = [geo.x, geo.y, geo.z]

                    references_list["sketch_points"].append({
                        "referenceId": refId,
                        "geometryType": "sketchPoint",
                        "sketchName": sketch.name,
                        "sketchPointIndex": pointIndex,
                        "location": loc
                    })


            references_list.pop("vertices")
            #references_list.pop("edges")
            references_list.pop("sketch_points")
            references_list.pop("faces")
            return json.dumps(references_list)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def create_joint_origin(self,
                            component_name: str = "comp1",
                            reference_id: str = "face|body0|face1",
                            origin_name: str = "topFaceCenter") -> str:

        """
        {
          "name": "create_joint_origin",
          "description": "Creates a Joint Origin in the specified component, attached to a reference (face/edge/vertex/sketchPoint) identified by reference_id. Names the Joint Origin as specified.",
          "parameters": {
            "type": "object",
            "properties": {
              "component_name": {
                "type": "string",
                "description": "Name of the Fusion 360 component in which to create the Joint Origin."
              },
              "reference_id": {
                "type": "string",
                "description": "ID string for the geometry reference. This typically comes from list_joint_origin_references()."
              },
              "origin_name": {
                "type": "string",
                "description": "A descriptive name for the newly created Joint Origin."
              }
            },
            "required": ["component_name", "reference_id", "origin_name"],
            "returns": {
              "type": "string",
              "description": "A message indicating success or any errors that occurred."
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

            # Find the target component by name
            targetComponent = None
            for comp in design.allComponents:
                if comp.name == component_name:
                    targetComponent = comp
                    break
            if not targetComponent:
                return f"Error: Component '{component_name}' not found."

            tokens = reference_id.split('|')
            if len(tokens) < 2:
                return f"Error: reference_id '{reference_id}' is not in the expected format."

            geometry_type = tokens[0]  # e.g. "face", "edge", "vertex", "sketchPoint"
            refGeom = None

            # We'll define a helper function to parse "bodyN" => integer N
            def parse_body_index(bodyTag):
                m = re.search(r"body(\d+)", bodyTag)
                return int(m.group(1)) if m else None

            if geometry_type in ["face", "edge", "vertex"]:
                if len(tokens) < 3:
                    return f"Error: reference_id '{reference_id}' missing 'bodyX|faceY/edgeY/vertexY'."

                bodyTag = tokens[1]           # e.g. "body0"
                fevTag = tokens[2]           # e.g. "face3", "edge1", or "vertex5"
                bodyIndex = parse_body_index(bodyTag)
                if bodyIndex is None:
                    return f"Error: Could not parse body index from '{bodyTag}'."

                fevMatch = re.search(r"(face|edge|vertex)(\d+)", fevTag)
                if not fevMatch:
                    return f"Error: Could not parse geometry index from '{fevTag}'."
                subType = fevMatch.group(1)  # "face", "edge", or "vertex"
                geomIndex = int(fevMatch.group(2))

                # Get the actual geometry
                bodies = targetComponent.bRepBodies
                if bodyIndex >= bodies.count:
                    return f"Error: Body index {bodyIndex} out of range."
                theBody = bodies.item(bodyIndex)

                if subType == "face":
                    if geomIndex >= theBody.faces.count:
                        return f"Error: Face index {geomIndex} out of range on body {bodyIndex}."

                    faceObj = theBody.faces.item(geomIndex)
                    faceGeo = faceObj.geometry

                    if isinstance(faceGeo, adsk.core.Plane ):
                        # This example assumes the face is planar
                        # For non-planar, use createByNonPlanarFace, etc.
                        planarFace = adsk.fusion.BRepFace.cast(faceObj)

                        if not planarFace or not planarFace.geometry or not isinstance(planarFace.geometry, adsk.core.Plane):
                            return "Error: The specified face is not planar. For non-planar, use createByNonPlanarFace, etc."

                        refGeom = adsk.fusion.JointGeometry.createByPlanarFace(
                            planarFace, #face
                            None, # edge
                            adsk.fusion.JointKeyPointTypes.CenterKeyPoint  # or MidPointKeyPoint, etc.
                        )

                    # center of cylinder
                    elif isinstance(faceGeo, adsk.core.Cylinder ):
                        # This example assumes the face is planar
                        # For non-planar, use createByNonPlanarFace, etc.
                        nonPlanarFace = adsk.fusion.BRepFace.cast(faceObj)
                        print(nonPlanarFace)

                        refGeom = adsk.fusion.JointGeometry.createByNonPlanarFace(
                            nonPlanarFace, #face
                            adsk.fusion.JointKeyPointTypes.MiddleKeyPoint  # or MidPointKeyPoint, etc.
                        )

                elif subType == "edge":

                    if geomIndex >= theBody.edges.count:
                        return f"Error: Edge index {geomIndex} out of range on body {bodyIndex}."
                    edgeObj = theBody.edges.item(geomIndex)
                    #print(edgeObj)


                    # TODO get edge type
                    try:
                        # Use createByCurve with a keypoint type; e.g. MiddleKeyPoint
                        refGeom = adsk.fusion.JointGeometry.createByCurve(
                            edgeObj,
                            adsk.fusion.JointKeyPointTypes.CenterKeyPoint
                        )
                    except Exception as e:
                        # Use createByCurve with a keypoint type; e.g. MiddleKeyPoint
                        refGeom = adsk.fusion.JointGeometry.createByCurve(
                            edgeObj,
                            adsk.fusion.JointKeyPointTypes.MiddleKeyPoint
                        )


                elif subType == "vertex":
                    if geomIndex >= theBody.vertices.count:
                        return f"Error: Vertex index {geomIndex} out of range on body {bodyIndex}."
                    vertexObj = theBody.vertices.item(geomIndex)
                    # For a vertex, use createByPoint
                    refGeom = adsk.fusion.JointGeometry.createByPoint(vertexObj)

            elif geometry_type == "sketchPoint":
                # Expect something like "sketchPoint|sketch0|point2"
                if len(tokens) < 3:
                    return f"Error: reference_id '{reference_id}' is missing 'sketchX|pointY'."

                sketchTag = tokens[1]  # e.g. "sketch0"
                pointTag = tokens[2]   # e.g. "point2"

                s_match = re.search(r"sketch(\d+)", sketchTag)
                p_match = re.search(r"point(\d+)", pointTag)
                if not s_match or not p_match:
                    return f"Error: Could not parse sketch/point indexes from '{sketchTag}', '{pointTag}'."
                sketchIndex = int(s_match.group(1))
                pointIndex = int(p_match.group(1))

                if sketchIndex >= targetComponent.sketches.count:
                    return f"Error: Sketch index {sketchIndex} out of range."
                theSketch = targetComponent.sketches.item(sketchIndex)
                if pointIndex >= theSketch.sketchPoints.count:
                    return f"Error: Sketch point index {pointIndex} out of range."

                skPointObj = theSketch.sketchPoints.item(pointIndex)
                refGeom = adsk.fusion.JointGeometry.createByPoint(skPointObj)

            else:
                return f"Error: Unrecognized geometry type '{geometry_type}' in reference_id '{reference_id}'."

            if not refGeom:
                return f"Error: Could not build JointGeometry for '{reference_id}'. Possibly non-planar or invalid geometry."

            # Now we create the Joint Origin
            joint_origins = targetComponent.jointOrigins
            jo_input = joint_origins.createInput(refGeom)
            # Optionally set orientation or offsets here, e.g.:
            # transform = adsk.core.Matrix3D.create()
            # transform.translation = adsk.core.Vector3D.create(0, 0, 1)  # offset 1 cm
            # jo_input.setByOffset(transform)

            # Add the new Joint Origin
            newJo = joint_origins.add(jo_input)
            newJo.name = origin_name

            return f"Joint Origin '{origin_name}' created for {reference_id} in component '{component_name}'."

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def create_joints_between_origins(self, joint_requests: list = [
            { "occurrence_1_name": "comp1:1",
             "joint_origin_1":"jointOrigin1",
             "occurrence_2_name":"comp2:1",
             "joint_origin_2":"jointOrigin2",
            "jointType":"RigidJointType",
                                      }]
                                      ) -> str:
        """
        {
          "name": "create_joints_between_origins",
          "description": "Creates new joints between pairs of existing jointOrigins. Each request specifies the path (or reference) to two JointOrigins and a joint type.",
          "parameters": {
            "type": "object",
            "properties": {
              "joint_requests": {
                "type": "array",
                "description": "An array of occurrence and joint names items",
                "items": {
                  "type": "object",
                  "properties": {
                    "occurrence_1_name": { "type": "string", "description": "Name of the first occurrence" },
                    "joint_origin_1": { "type": "string", "description": "Name of the first joint origin." },
                    "occurrence_2_name": { "type": "string", "description": "Name of the second occurrence" },
                    "joint_origin_2": { "type": "string", "description": "Name of the second joint origin." },
                    "jointType": {
                      "type": "string",
                      "description": "The type of joint: 'RigidJointType', 'RevoluteJointType', etc."
                    }
                  },
                  "required": ["occurrence_1_name", "joint_origin_1", "occurrence_2_name", "joint_origin_2", "jointType"]
                }
              }
            },
            "required": ["joint_requests"],
            "returns": {
              "type": "string",
              "description": "A summary of created joints or errors encountered."
            }
          }
        }
        """

        try:
            if not joint_requests or not isinstance(joint_requests, list):
                return "Error: Must provide an array of joint requests."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)
            root_comp = design.rootComponent

            # A mapping from string to the Fusion 360 JointTypes enumerations
            joint_type_map = {
                "RigidJointType": adsk.fusion.JointTypes.RigidJointType,
                "RevoluteJointType": adsk.fusion.JointTypes.RevoluteJointType,
                "SliderJointType": adsk.fusion.JointTypes.SliderJointType,
                "CylindricalJointType": adsk.fusion.JointTypes.CylindricalJointType,
                "PinSlotJointType": adsk.fusion.JointTypes.PinSlotJointType,
                "PlanarJointType": adsk.fusion.JointTypes.PlanarJointType,
                "BallJointType": adsk.fusion.JointTypes.BallJointType
            }

            results = []

            # A helper to find a joint origin by name or path (assuming unique naming)
            def find_joint_origin_by_name(occ, name_str):
                # Search in all components
                for j_origin in occ.component.jointOrigins:
                    print(j_origin.name)
                    if j_origin.name == name_str:
                        return j_origin

                return None


            for request in joint_requests:
                print(request)
                occ_1_name = request.get("occurrence_1_name")
                j1_name = request.get("joint_origin_1")
                occ_2_name = request.get("occurrence_2_name")
                j2_name = request.get("joint_origin_2")

                j_type_str = request.get("jointType")

                occ1, errors, = self._find_occurrence_by_name(occ_1_name)
                if not occ1:
                    results.append(errors)
                    continue
                occ2, errors, = self._find_occurrence_by_name(occ_2_name)
                if not occ2:
                    results.append(errors)
                    continue


                if not (j1_name and j2_name and j_type_str):
                    results.append(f"Error: Missing fields in {request}")
                    continue

                # Map the jointType string
                if j_type_str not in joint_type_map:
                    results.append(f"Error: Unknown jointType '{j_type_str}' in {request}")
                    continue
                the_joint_type = joint_type_map[j_type_str]

                # Find the joint origins by their name or path
                joint_origin_1 = find_joint_origin_by_name(occ1, j1_name)
                joint_origin_2 = find_joint_origin_by_name(occ2, j2_name)

                if not joint_origin_1 or not joint_origin_2:
                    results.append(f"Error: Could not find one or both JointOrigins '{j1_name}', '{j2_name}'.")
                    continue

                # Create a JointInput
                #joint_origin_1 = joint_origin_1.occurrenceForGeometry(occ1)
                #joint_origin_2 = joint_origin_2.occurrenceForGeometry(occ2)

                joints_collection = root_comp.joints
                j_input = joints_collection.createInput(
                    joint_origin_1, joint_origin_2
                )

                # TODO need to handle all joint types here
                #j_input.setAsStandardJoint(the_joint_type)
                j_input.setAsRigidJointMotion()

                # Add the joint
                try:
                    new_joint = joints_collection.add(j_input)
                    results.append(
                        f"Joint of type '{j_type_str}' created between '{j1_name}' and '{j2_name}'."
                    )
                except Exception as e:
                    results.append(f"Error creating joint between '{j1_name}' and '{j2_name}': {str(e)}")

            return "\n".join(results)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def modify_joint_origin(self,
                            joint_origin_name: str = None,
                            new_geometry: dict = None,
                            new_orientation: dict = None) -> str:
        """
        {
          "name": "modify_joint_origin",
          "description": "Modifies an existing joint origin, including its attachment point (geometry) and orientation (offset or angle).",
          "parameters": {
            "type": "object",
            "properties": {
              "joint_origin_name": {
                "type": "string",
                "description": "Name of the joint origin to modify."
              },
              "new_geometry": {
                "type": "object",
                "description": "An optional specification of new geometry for the joint origin. For example: { 'type': 'face', 'component_name': 'comp1', 'body_index': 0, 'face_index': 2 } or { 'type': 'sketchPoint', ... }"
              },
              "new_orientation": {
                "type": "object",
                "description": "An optional specification of transform or offset. E.g. { 'offsetX': 1.0, 'offsetY': 0.5, 'offsetZ': 0 } in cm or an angle in degrees."
              }
            },
            "required": ["joint_origin_name"],
            "returns": {
              "type": "string",
              "description": "A success or error message."
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

            if not joint_origin_name:
                return "Error: joint_origin_name is required."

            # Locate the joint origin by name
            target_jo = None
            for comp in design.allComponents:
                for jo in comp.jointOrigins:
                    if jo.name == joint_origin_name:
                        target_jo = jo
                        break
                if target_jo:
                    break

            if not target_jo:
                return f"Error: JointOrigin '{joint_origin_name}' not found."

            # We retrieve the existing definition
            jo_def = target_jo.definition
            # For example, jo_def is typically a "JointOriginDefinition" object, which might be
            # an OffsetPlaneJointOriginDefinition, etc.

            # 1) If new_geometry is specified, reattach to new geometry
            if new_geometry and isinstance(new_geometry, dict):
                # We'll do a simplistic approach; you can adapt to your geometry approach
                # e.g. re-creating a JointGeometry by face/edge/sketchPoint, etc.
                new_geom_ref = None
                geom_type = new_geometry.get("type")  # e.g. "face", "edge", "sketchPoint"
                comp_name = new_geometry.get("component_name")
                body_index = new_geometry.get("body_index")
                face_index = new_geometry.get("face_index")
                # etc. This part is flexible, depending on how you define your references.

                # Example: if we detect "face" and the user provided body_index, face_index
                if geom_type == "face" and comp_name is not None and body_index is not None and face_index is not None:
                    # Find the component
                    new_comp = None
                    for c in design.allComponents:
                        if c.name == comp_name:
                            new_comp = c
                            break
                    if not new_comp:
                        return f"Error: Could not find component '{comp_name}' for new geometry."

                    if body_index < 0 or body_index >= new_comp.bRepBodies.count:
                        return f"Error: body_index {body_index} out of range in comp '{comp_name}'."

                    the_body = new_comp.bRepBodies.item(body_index)
                    if face_index < 0 or face_index >= the_body.faces.count:
                        return f"Error: face_index {face_index} out of range in body {body_index}."

                    the_face = the_body.faces.item(face_index)
                    # Create a new JointGeometry
                    plane_face = adsk.fusion.BRepFace.cast(the_face)
                    if plane_face and isinstance(plane_face.geometry, adsk.core.Plane):
                        new_geom_ref = adsk.fusion.JointGeometry.createByPlanarFace(
                            plane_face,
                            adsk.fusion.JointKeyPointTypes.CenterKeyPoint
                        )
                    else:
                        return "Error: Only planar faces handled in this sample."

                # If new_geom_ref is found, update definition
                if new_geom_ref:
                    # Reattach
                    jo_def.reattach(new_geom_ref)

            # 2) If new_orientation is specified, apply offset or angles
            #    For example, if user provides an offsetX, offsetY, offsetZ in cm
            #    or a rotation angle in degrees about some axis, etc.
            if new_orientation and isinstance(new_orientation, dict):
                # We'll do a basic offset approach.
                ox = new_orientation.get("offsetX", 0.0)
                oy = new_orientation.get("offsetY", 0.0)
                oz = new_orientation.get("offsetZ", 0.0)

                if abs(ox) > 1e-7 or abs(oy) > 1e-7 or abs(oz) > 1e-7:
                    offset_transform = adsk.core.Matrix3D.create()
                    offset_transform.translation = adsk.core.Vector3D.create(ox, oy, oz)
                    # The setByOffset method replaces the existing orientation
                    jo_def.setByOffset(offset_transform)

                # If you also want angles, you'd do a rotation in the transform or use
                # jo_def.setByXXX(...). The specifics can be expanded if needed.

            return f"Joint Origin '{joint_origin_name}' modified successfully."

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()




class Timeline(ToolCollection):

    #@ToolCollection.tool_call
    def list_timeline_info(self) -> str:
        """
            {
              "name": "list_timeline_info",
              "description": "Returns a JSON array describing all items in the Fusion 360 timeline, including entity info, errors/warnings, healthState, etc.",
              "parameters": {
                "type": "object",
                "properties": {
                },
                "required": [],
                "returns": {
                  "type": "string",
                  "description": "A JSON array; each entry includes timeline item data such as index, name, entityType, healthState, errorOrWarningMessage, etc."
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
            timeline = design.timeline

            timeline_info = []

            for i in range(timeline.count):
                t_item = timeline.item(i)
                if not t_item:
                    continue

                # Collect basic info
                item_data = {
                    "index": t_item.index,
                    "name": t_item.name,
                    "isSuppressed": t_item.isSuppressed,
                    "healthState": str(t_item.healthState),          # e.g. 'HealthStateError', 'HealthStateOk'
                    "errorOrWarningMessage": t_item.errorOrWarningMessage,
                }

                # Parent group reference
                if t_item.parentGroup:
                    item_data["parentGroupIndex"] = t_item.parentGroup.index
                    item_data["parentGroupName"] = t_item.parentGroup.name

                # Entity info
                entity = t_item.entity
                if entity:
                    # We'll store a few general properties if available
                    entity_type = entity.objectType  # e.g. 'adsk::fusion::ExtrudeFeature'
                    item_data["entityType"] = entity_type

                    # Many entities have a "name" property, but not all. We'll try/catch.
                    entity_name = getattr(entity, "name", None)
                    if entity_name:
                        item_data["entityName"] = entity_name

                    # Optionally gather more info if you like:
                    # e.g. if entity_type indicates a feature, you could store
                    # entity.isSuppressed or others. Just be sure to check for availability.
                else:
                    item_data["entityType"] = None  # E.g., might be a group or unknown.

                timeline_info.append(item_data)

            return json.dumps(timeline_info)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()



    @ToolCollection.tool_call
    def roll_back_to_timeline(self, index_to_rollback: int = 0) -> str:
        """
        {
          "name": "roll_back_to_timeline",
          "description": "Rolls the design's timeline marker back (or forward) to the specified index, effectively suppressing all features after that index.",
          "parameters": {
            "type": "object",
            "properties": {
              "index_to_rollback": {
                "type": "number",
                "description": "The timeline index to move the marker to. Items after this index will be suppressed in the UI."
              }
            },
            "required": ["index_to_rollback"],
            "returns": {
              "type": "string",
              "description": "A message indicating success or any error encountered."
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
            timeline = design.timeline

            if index_to_rollback < 0 or index_to_rollback >= timeline.count:
                return f"Error: index_to_rollback {index_to_rollback} out of range (0..{timeline.count - 1})."

            # Move the marker position
            timeline.markerPosition = index_to_rollback
            return f"Timeline marker moved to index {index_to_rollback}."

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()



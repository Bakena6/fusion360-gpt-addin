# cad design

import adsk.core
import adsk.fusion
import adsk.cam
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
import functools
import hashlib
import base64
import re

from ... import config
from ...lib import fusion360utils as futil
from .shared import ToolCollection

def print(string):
    """redefine print for fusion env"""
    futil.log(str(string))

print(f"RELOADED: {__name__.split("%2F")[-1]}")


class ModifyObjects(ToolCollection):



    @ToolCollection.tool_call
    def fillet_or_chamfer_edges(self,
                               component_entity_token: str ="",
                               edge_tokens_list: list = [""],
                               operation_value: float = 0.2,
                               operation_type: str = "fillet") -> str:
        """
        {
          "name": "fillet_or_chamfer_edges",
          "description": "Applies either a fillet or chamfer to the specified edges of a body.",
          "parameters": {
            "type": "object",
            "properties": {

              "component_entity_token": {
                "type": "string",
                "description": "The enting token of the associated component"
              },
              "edge_tokens_list": {
                "type": "array",
                "description": "An array of entityTokens, each represting a bRepEdge",
                "items": { "type": "string" }
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
            "required": ["component_entity_token", "edge_tokens_list", "operation_value", "operation_type"],
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
            targetComponent = self.get_hash_obj(component_entity_token)
            if not targetComponent:
                return f"Error: No component found for for enityToken: '{component_entity_token}'."

            edge_collection = adsk.core.ObjectCollection.create()
            invalid_tokens = []
            for edge_token in edge_tokens_list:
                edge = self.get_hash_obj(edge_token)
                if edge == None:
                    invalid_tokens.append(edge_token)
                    continue

                edge_collection.add(edge)

            # Create either a fillet or a chamfer
            if operation_type == "fillet":
                try:
                    fillet_feats = targetComponent.features.filletFeatures
                    fillet_input = fillet_feats.createInput()
                    # Construct the radius ValueInput
                    radius_val = adsk.core.ValueInput.createByReal(float(operation_value))
                    # Add all edges to a single radius set
                    fillet_input.addConstantRadiusEdgeSet(edge_collection, radius_val, True)
                    fillet_feats.add(fillet_input)
                    msg = f"Success: Fillet applied with radius {operation_value} to {len(edge_tokens_list)} edges."
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
                    msg = f"Success: Chamfer applied with radius {operation_value} to {len(edge_tokens_list)} edges."
                except Exception as e:
                    return f"Error: Error creating chamfer: {e}"

            # Include any invalid edge indexes in the output message for clarity
            if invalid_tokens:
                msg += f" Some invalid edges were ignored: {invalid_tokens}"
            return msg

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def mirror_body_in_component(
        self,
        component_entity_token: str = "",
        body_entity_token: str = "",
        mirror_plane_entity_token: str = "",
        operation_type: str = "JoinFeatureOperation",
    ) -> str:
        """
        {
          "name": "mirror_body_in_component",
          "description": "Mirrors a specified body in a component along one of the component's planes (XY, XZ, YZ) or a planar face in the body by face index. It creates a MirrorFeature in the timeline.",
          "parameters": {
            "type": "object",
            "properties": {
              "component_entity_token": {
                "type": "string",
                "description": "The entityToken for the component containing the target body."
              },
              "body_entity_token": {
                "type": "string",
                "description": "The entityToken for the BRepBody to mirror."
              },

              "mirror_plane_entity_token": {
                "type": "string",
                "description": "The entityToken of the plane to mirror about."
              },
              "operation_type": {
                "type": "string",
                "description": "Either 'JoinFeatureOperation' or 'NewBodyFeatureOperation'.",
                "enum": [
                  "JoinFeatureOperation",
                  "NewBodyFeatureOperation"
                ]
              }
            },
            "required": ["component_entity_token", "body_entity_token", "mirror_plane_entity_token", "operation_type"],
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
            targetComponent = self.get_hash_obj(component_entity_token)
            if not targetComponent:
                return f"Error: No component found for entityToken: '{component_entity_token}'"

            body_to_mirror = self.get_hash_obj(body_entity_token)
            if not body_to_mirror:
                return f"Error: No body found for entityToken: '{body_entity_token}'"

            mirror_plane_obj = self.get_hash_obj(mirror_plane_entity_token)
            if not mirror_plane_obj:
                return f"Error: No mirror plane found for entityToken: '{mirror_plane_entity_token}'"

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
                return f"Success: Mirrored body '{body_to_mirror.name}' in component '{targetComponent.name}'"

            except Exception as e:
                return f"Error: creating mirror feature: {str(e)}"

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

class CreateObjects(ToolCollection):

    def _get_operation_obj(self, operation_type):

        # Map the operation_type string to the Fusion enum
        operation_map = {
            "CutFeatureOperation": adsk.fusion.FeatureOperations.CutFeatureOperation,
            "IntersectFeatureOperation": adsk.fusion.FeatureOperations.IntersectFeatureOperation,
            "JoinFeatureOperation": adsk.fusion.FeatureOperations.JoinFeatureOperation,
            "NewBodyFeatureOperation": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            "NewComponentFeatureOperation": adsk.fusion.FeatureOperations.NewComponentFeatureOperation
        }

        operation_obj = operation_map.get(operation_type)
        errors = None

        if operation_type is None:
            errors = f"Error: Unknown operation_type '{operation_type}', Valid: {', '.join(operation_map.keys())}."

        return operation_obj, errors


    @ToolCollection.tool_call
    def extrude_profiles(
        self,
        profile_entity_tokens: list = [""],
        extrude_distance: float = 1,
        operation_type: str = "NewBodyFeatureOperation",
        start_extent: float = 0.0,
        taper_angle: float = 0.0
    ) -> str:
        """
        {
            "name": "extrude_profiles",
            "description": "Extrudes one or more profiles. The operation_type parameter selects which FeatureOperation to use. The unit for extrudeDistance and start_extent is centimeters, and taper_angle is in degrees (can be positive or negative).",
            "parameters": {
                "type": "object",
                "properties": {
                    "profile_entity_tokens": {
                        "type": "array",
                        "items": { "type": "string" },
                        "description": "A list of profile entityTokens to extrude."
                    },
                    "extrude_distance": {
                        "type": "string",
                        "description": "The distance to extrude the profiles."
                    },

                    "operation_type": {
                        "type": "string",
                        "enum": [
                            "CutFeatureOperation",
                            "IntersectFeatureOperation",
                            "JoinFeatureOperation",
                            "NewBodyFeatureOperation",
                            "NewComponentFeatureOperation"
                        ],
                        "description": "Specifies the Fusion 360 FeatureOperation to apply."
                    },
                    "start_extent": {
                        "type": "number",
                        "description": "Offset distance in centimeters from the sketch plane to start the extrude. Can be positive or negative. Default 0."
                    },
                    "taper_angle": {
                        "type": "number",
                        "description": "Taper angle (in degrees). Positive or negative. Default 0."
                    }
                },
                "required": ["profile_entity_tokens", "extrude_distance", "start_extent", "taper_angle"],
                "returns": {
                    "type": "string",
                    "description": "A message indicating whether the extrude operations completed successfully or not."
                }
            }
        }

        """
        try:
            # A small dictionary to map string inputs to the appropriate enumerations.
            operation_map = {
                "CutFeatureOperation": adsk.fusion.FeatureOperations.CutFeatureOperation,
                "IntersectFeatureOperation": adsk.fusion.FeatureOperations.IntersectFeatureOperation,
                "JoinFeatureOperation": adsk.fusion.FeatureOperations.JoinFeatureOperation,
                "NewBodyFeatureOperation": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                "NewComponentFeatureOperation": adsk.fusion.FeatureOperations.NewComponentFeatureOperation
            }

            # Validate the requested operation_type.
            if operation_type not in operation_map:
                return (f'Error: operation_type "{operation_type}" is not recognized. '
                        f'Valid options are: {", ".join(operation_map.keys())}.')

            # Access the active design.
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)

            # find the target component by name (assuming you have a local helper method).
            targetComponent = self.get_hash_obj(profile_entity_tokens[0]).parentSketch.parentComponent
            if not targetComponent:
                return f"Error: No component found for for enityToken: '{component_entity_token}'."

            if len(profile_entity_tokens) == 0:
                return f"Error: '{component_entity_tokens}' Argument 'profile_entity_tokens' must not be empty."

            # Prepare extrude feature objects
            extrudes = targetComponent.features.extrudeFeatures
            results = {}

            # Convert extrudeDist (cm) to internal real value
            distanceVal = adsk.core.ValueInput.createByReal(float(extrude_distance))

            profile_collection = adsk.core.ObjectCollection.create()
            for profile_entity_token in profile_entity_tokens:
                profile = self.get_hash_obj(profile_entity_token)

                if profile is None:
                    results["Errors"] = f"Error: No profile found for enityToken '{profile_entity_token}'."
                    continue

                profile_collection.add(profile)

            try:
                # Create the extrude feature input with the requested operation type.
                extInput = extrudes.createInput(profile_collection, operation_map[operation_type])

                # 1) Set an offset start extent if requested
                if abs(start_extent) > 1e-7:  # effectively non-zero
                    offsetVal = adsk.core.ValueInput.createByReal(float(start_extent))
                    offsetDef = adsk.fusion.OffsetStartDefinition.create(offsetVal)
                    extInput.startExtent = offsetDef

                # 2) Set the taper angle (in degrees) if non-zero
                if abs(taper_angle) > 1e-7:
                    # Use createByString for degrees (e.g., "15 deg")
                    angleVal = adsk.core.ValueInput.createByString(f"{taper_angle} deg")
                    extInput.taperAngle = angleVal

                # 3) Set the extent as a one-side distance.
                extInput.setDistanceExtent(False, distanceVal)

                # Add the extrude feature
                extrude_results = extrudes.add(extInput)

                new_bodies = self.object_creation_response(extrude_results)

                results["Results"] = f"Success: Extruded '{profile_collection.count}' profiles by '{extrude_distance}', startExtent={start_extent}, taper={taper_angle} with '{operation_type}'."

                results["New BRepBodies"] = new_bodies


            except Exception as e:
                results["Errors"] = f"Error: Could not extrude profile '{profile_entity_token}'. Reason: {e}"

            # Combine all messages.
            return json.dumps(results)

        except Exception as e:
            return f"Error: An unexpected exception occurred: {e}"


    @ToolCollection.tool_call
    def thin_extrude_lines(self,
                           line_token_list: list = [],
                           thin_extrude_width: float = 0.1,
                           thin_extrude_height: float = 1.0,
                           operation_type: str = "NewBodyFeatureOperation",
                           wall_location: str = "side1",
                           taper_angle: float = 0.0) -> str:
        """
        {
          "name": "thin_extrude_lines",
          "description": "Performs a 'Thin Extrude' on a list of open lines. Each line is referenced by a token. A new extrude feature is created for each open profile.",
          "parameters": {
            "type": "object",
            "properties": {
              "line_token_list": {
                "type": "array",
                "description": "A list of entity tokens referencing Fusion 360 line objects (SketchLine).",
                "items": { "type": "string" }
              },
              "thin_extrude_width": {
                "type": "number",
                "description": "Thickness of the thin extrude (in current design length units)."
              },
              "thin_extrude_height": {
                "type": "number",
                "description": "How far to extrude (in current design length units)."
              },
              "operation_type": {
                "type": "string",
                "enum": ["CutFeatureOperation", "JoinFeatureOperation", "IntersectFeatureOperation", "NewBodyFeatureOperation", "NewComponentFeatureOperation"],
                "description": "Feature operation: CutFeatureOperation, JoinFeatureOperation, IntersectFeatureOperation, NewBodyFeatureOperation, NewComponentFeatureOperation."
              },
              "wall_location": {
                "type": "string",
                "description": "Where to apply the thickness. One of: side1, side2, center."
              },
              "taper_angle": {
                "type": "number",
                "description": "Taper angle in degrees (positive or negative)."
              }
            },
            "required": ["line_token_list", "thin_extrude_width", "thin_extrude_height"],
            "returns": {
              "type": "string",
              "description": "JSON string mapping each extrude result or an error message."
            }
          }
        }
        """
        try:
            # Basic validation of the inputs
            if not line_token_list or not isinstance(line_token_list, list):
                return "Error: line_token_list must be a non-empty list of line entity tokens."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)
            root_comp = design.rootComponent

            targetComponent = self.get_hash_obj(line_token_list[0]).parentSketch.parentComponent
            # find the target component by name (assuming you have a local helper method).
            if not targetComponent:
                return f"Error: No component found"

            # FeatureOperations mapping
            operation_map = {
                "CutFeatureOperation": adsk.fusion.FeatureOperations.CutFeatureOperation,
                "IntersectFeatureOperation": adsk.fusion.FeatureOperations.IntersectFeatureOperation,
                "JoinFeatureOperation": adsk.fusion.FeatureOperations.JoinFeatureOperation,
                "NewBodyFeatureOperation": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                "NewComponentFeatureOperation": adsk.fusion.FeatureOperations.NewComponentFeatureOperation
            }
            if operation_type not in operation_map:
                return (f"Error: Unknown operation_type '{operation_type}'. "
                        f"Valid: {', '.join(operation_map.keys())}.")

            wall_map = {
                "side1": adsk.fusion.ThinExtrudeWallLocation.Side1,
                "side2": adsk.fusion.ThinExtrudeWallLocation.Side2,
                "center": adsk.fusion.ThinExtrudeWallLocation.Center
            }
            if wall_location not in wall_map:
                return ("Error: wall_location must be one of 'side1', 'side2', or 'center'.")

            # Prepare extrude feature objects
            extrudes = targetComponent.features.extrudeFeatures

            results = {}

            profile_collection = adsk.core.ObjectCollection.create()
            # Collect the line objects from the tokens
            for index, token in enumerate(line_token_list):

                line_obj = self.get_hash_obj(token)  # or your design.findEntityByToken(token)

                if not line_obj:
                    results[token] = f"Error: no object found for token '{token}'."
                    continue

                open_line_profile = targetComponent.createOpenProfile(line_obj, False)

                profile_collection.add(open_line_profile)

                results[token] = "Line added successfully."

            # If no valid lines found, stop
            if profile_collection.count == 0:
                return json.dumps(results)

             #Create the extrude input
            ext_input = extrudes.createInput(
                #open_profile,
                profile_collection,
                operation_map[operation_type]
            )

            # We'll also create the thickness ValueInput, plus the taper angle.
            distance_val = adsk.core.ValueInput.createByReal(float(thin_extrude_height))
            thickness_val = adsk.core.ValueInput.createByReal(float(thin_extrude_width))
            angle_val = adsk.core.ValueInput.createByString(f"{taper_angle} deg")
            wall_location_obj = wall_map[wall_location]

            ext_input.setThinExtrude(wall_location_obj, thickness_val)

            # 3) Set the extent as a one-side distance.
            ext_input.setDistanceExtent(False, distance_val)

            new_features = extrudes.add(ext_input)

            new_bodies = self.object_creation_response(new_features)

            results["Results"] = str(new_features)
            results["New BRepBodies"] = new_bodies

            return json.dumps(results)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


    @ToolCollection.tool_call
    def revolve_profiles(
        self,
        profile_entity_tokens: list = [""],
        revolve_axis_entity_token: str = "",
        revolve_degrees: float = 180.0,
        operation_type: str = "NewBodyFeatureOperation"
    ) -> str:
        """
        {
          "name": "revolve_profiles",
          "description": "Revolves a specified sketch profile(s) around an axis.",
          "parameters": {
            "type": "object",
            "properties": {

               "profile_entity_tokens": {
                   "type": "array",
                   "items": { "type": "string" },
                   "description": "A list of profile entityTokens to extrude."
               },
              "revolve_axis_entity_token": {
                "type": "string",
                "description": "Entity token representing the axis to revolve around"
              },
              "revolve_degrees": {
                "type": "number",
                "description": "Angle (in degrees) to revolve. Can be positive or negative. Default 180."
              },
              "operation_type": {
                "type": "string",
                "enum": [
                  "CutFeatureOperation",
                  "IntersectFeatureOperation",
                  "JoinFeatureOperation",
                  "NewBodyFeatureOperation",
                  "NewComponentFeatureOperation"
                ],
                "description": "Specifies the Fusion 360 FeatureOperation. Default 'NewBodyFeatureOperation'."
              }
            },
            "required": ["profile_entity_tokens", "revolve_axis_entity_token", "revolve_axis", "revolve_degrees"],
            "returns": {
              "type": "string",
              "description": "A message indicating whether the revolve operation completed successfully or not."
            }
          }
        }
        """

        try:
            # Maps the string operation to the Fusion 360 enum
            operation_map = {
                "CutFeatureOperation": adsk.fusion.FeatureOperations.CutFeatureOperation,
                "IntersectFeatureOperation": adsk.fusion.FeatureOperations.IntersectFeatureOperation,
                "JoinFeatureOperation": adsk.fusion.FeatureOperations.JoinFeatureOperation,
                "NewBodyFeatureOperation": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
                "NewComponentFeatureOperation": adsk.fusion.FeatureOperations.NewComponentFeatureOperation
            }

            if operation_type not in operation_map:
                return (f'Error: operation_type "{operation_type}" is not recognized. '
                        f'Valid: {", ".join(operation_map.keys())}.')

            # Access the active design
            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            design = adsk.fusion.Design.cast(product)
            if not design:
                return "Error: No active Fusion 360 design found."

            targetSketch = self.get_hash_obj(profile_entity_tokens[0]).parentSketch
            if not targetSketch:
                return "Error: No target sketch"

            targetComponent = self.get_hash_obj(profile_entity_tokens[0]).parentSketch.parentComponent
            if not targetComponent:
                return "Error: No target componet"



            revolveAxisObj = self.get_hash_obj(revolve_axis_entity_token)

            profile_collection = adsk.core.ObjectCollection.create()
            for profile_entity_token in profile_entity_tokens:
                profile = self.get_hash_obj(profile_entity_token)
                if profile is None:
                    results.append(f"Error: Invalid profile index {profile_entity_token}.")
                    continue
                profile_collection.add(profile)

            # Create revolve input
            revolve_feats = targetComponent.features.revolveFeatures
            rev_input = revolve_feats.createInput(profile_collection, revolveAxisObj, operation_map[operation_type])
            # One-sided revolve angle
            angleVal = adsk.core.ValueInput.createByString(f"{revolve_degrees} deg")
            rev_input.setAngleExtent(False, angleVal)


            try:
                revolve_result = revolve_feats.add(rev_input)

                new_objects = self.object_creation_response(revolve_result)

                results = {}
                msg = f"Revolved profiles in sketch '{targetSketch.name}' by '{revolve_degrees}' degrees using '{operation_type}'."

                results["Message"] = msg
                results["Objects"] = new_objects

                return json.dumps(results)


            except Exception as e:
                return f"Error creating revolve: {e}"

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()



    @ToolCollection.tool_call
    def copy_component_as_new(
        self,
        source_component_entity_token: str="",
        parent_component_entity_token: str="",
        new_component_name: str="new_comp_1") -> str:

        """
            {
                "name": "copy_component_as_new",
                "description": "Creates a completely new component by copying the geometry of an existing component. The copied component is inserted as a new occurrence in the target parent component, but is otherwise independent of the source. The newly created component will be renamed to the provided new_component_name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source_component_entity_token": {
                            "type": "string",
                            "description": "Entity token representing the existing Fusion 360 component to be copied."
                        },
                        "parent_component_entity_token": {
                            "type": "string",
                            "description": "Entity token representing parent component for the newly copied component."
                        },
                        "new_component_name": {
                            "type": "string",
                            "description": "The desired name for the newly created component copy."
                        }
                    },
                    "required": ["source_component_entity_token", "parent_component_entity_token", "new_component_name"],
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

            # Find the target component by name (assuming you have a helper method).
            sourceComp = self.get_hash_obj(source_component_entity_token)
            if not sourceComp:
                return f"Error: No source component found for entityToken: '{source_component_entity_token}'"
            source_component_name = sourceComp.name

            # Find the target component by name (assuming you have a helper method).
            parentComp = self.get_hash_obj(parent_component_entity_token)
            if not parentComp:
                return f"Error: No parent component found for entityToken: '{parent_component_entity_token}'"
            parent_component_name = parentComp.name

            # Create a new, independent copy of the source component
            transform = adsk.core.Matrix3D.create()  # Identity transform
            new_occurrence = parentComp.occurrences.addNewComponentCopy(sourceComp, transform)
            new_comp = new_occurrence.component

            # Rename the newly created component
            new_comp.name = new_component_name
            new_comp_entity_token = self.set_obj_hash(new_comp)
            new_occ_entity_token = self.set_obj_hash(new_occurrence)

            return f"Success: Created a new, independent copy of '{source_component_name}' into '{parent_component_name}' named '{new_component_name}'. The new component entityToken is '{new_comp_entity_token}', and the new occurrence entityToken is '{new_occ_entity_token}'."


        except Exception as e:
            return f"Error: Failed to copy component with token '{source_component_entity_token}' as a new component:\n{e}"

    @ToolCollection.tool_call
    def copy_occurrence(
        self,
        source_component_entity_token: str="",
        parent_component_entity_token: str=""
    ) -> str:

        """
            {
                "name": "copy_occurrence",
                "description": "Creates a new occurrence of an existing component inside another parent component. This effectively 'copies' the geometry by referencing the same underlying component in a new location.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source_component_entity_token": {
                            "type": "string",
                            "description": "The entityToken representing the existing Fusion 360 component to be copied."
                        },
                        "parent_component_entity_token": {
                            "type": "string",
                            "description": "The entityToken representing the parent component for the new copy."
                        }
                    },
                    "required": ["source_component_entity_token", "parent_component_entity_token"],
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


            # Find the target component by name (assuming you have a helper method).
            sourceComp = self.get_hash_obj(source_component_entity_token)
            if not sourceComp:
                return f"Error: No source component found for entityToken: '{source_component_entity_token}'"
            source_component_name = sourceComp.name

            # Find the target component by name (assuming you have a helper method).
            parentComp = self.get_hash_obj(parent_component_entity_token)
            if not parentComp:
                return f"Error: No parent component found for entityToken: '{parent_component_entity_token}'"
            parent_component_name = parentComp.name

            # Create a new occurrence of the source component in the target parent component
            transform = adsk.core.Matrix3D.create()  # Identity transform (no rotation, no translation)
            new_occurrence = parentComp.occurrences.addExistingComponent(sourceComp, transform)

            new_occ_entity_token = self.set_obj_hash(new_occurrence)

            return f"Success: copied '{source_component_name}' into '{parent_component_name}'. The new occurrence's entityToken is '{new_occ_entity_token}'"

        except Exception as e:
            return f"Error: Failed to copy component with token '{source_component_entity_token}' as a new component:\n{e}"


    @ToolCollection.tool_call
    def create_pipe_from_lines(self,
                              line_token_list: list = [""],
                              pipe_diameter: float = 1.0,
                              operation_type: str = "NewBodyFeatureOperation") -> str:
        """
        {
          "name": "create_pipe_from_lines",
          "description": "Creates a Pipe feature on each SketchLine in the list, each line is referenced by a token.",

          "parameters": {
            "type": "object",
            "properties": {
              "line_token_list": {
                "type": "array",
                "description": "A list of entity tokens referencing SketchLine objects.",
                "items": { "type": "string" }
              },
              "pipe_diameter": {
                "type": "number",
                "description": "Diameter of the pipe in the current design's length units."
              },
              "operation_type": {
                "type": "string",
                "description": "Feature operation: CutFeatureOperation, JoinFeatureOperation, IntersectFeatureOperation, NewBodyFeatureOperation, NewComponentFeatureOperation."
              }
            },
            "required": ["line_token_list", "pipe_diameter"],
            "returns": {
              "type": "string",
              "description": "A JSON object mapping each line token to a success or error message."
            }
          }
        }
        """

        results = {}
        try:
            if not line_token_list or not isinstance(line_token_list, list):
                return "Error: line_token_list must be a non-empty list of token strings."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)
            #root_comp = design.rootComponent

            operation_obj, errors = self._get_operation_obj(operation_type)
            if operation_obj is None:
                return errors

            targetComponent = self.get_hash_obj(line_token_list[0]).parentSketch.parentComponent
            # find the target component by name (assuming you have a local helper method).
            if not targetComponent:
                return f"Error: No component found"

            # Convert extrudeDist (cm) to internal real value
            thickness = adsk.core.ValueInput.createByReal(float( pipe_diameter))

            # Prepare pipe feature objects
            pipe_features = targetComponent.features.pipeFeatures

            for token in line_token_list:
                line_obj = self.get_hash_obj(token)

                if not line_obj:
                    results[token] = f"Error: no object found for token '{token}'."
                    continue

                if not isinstance(line_obj, adsk.fusion.SketchLine):
                    results[token] = f"Error: object for token '{token}' is not a SketchLine."
                    continue

                # 2) Create a Path from this line
                path_entity = adsk.core.ObjectCollection.create()
                path_entity.add(line_obj)
                # Create a path object
                path = targetComponent.features.createPath(path_entity, False)  # isChain = False

                pipe_input = pipe_features.createInput(path, operation_obj)
                pipe_input.sectionSize = thickness

                #creationOccurrence

                try:
                    pipe_feature = pipe_features.add(pipe_input)

                    results[token] = f"Success: Created pipe with diameter={pipe_diameter} using line token '{token}'."
                except Exception as e:
                    results[token] = f"Error creating sweep for line token '{token}': {str(e)}"



            return json.dumps(results)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


    #@ToolCollection.tool_call
    def create_spheres_from_points(self,
                                   point_token_list: list = None,
                                   sphere_radius: float = 1.0) -> str:
        """
        {
          "name": "create_spheres_from_points",
          "description": "Creates a set of sphere bodies from a list of Point3D references using TemporaryBRepManager. Adds all spheres to a single Base Feature. Returns JSON with body tokens for each sphere or any errors.",
          "parameters": {
            "type": "object",
            "properties": {
              "point_token_list": {
                "type": "array",
                "description": "A list of tokens referencing adsk.core.Point3D objects, each specifying a center for a sphere.",
                "items": { "type": "string" }
              },
              "sphere_radius": {
                "type": "number",
                "description": "The radius of each sphere in the current design's length units."
              }
            },
            "required": ["point_token_list", "sphere_radius"],
            "returns": {
              "type": "string",
              "description": "A JSON object mapping each token to success or error, plus a 'baseFeatureToken' referencing the base feature, and new body tokens if desired."
            }
          }
        }
        """
        try:
            if not point_token_list or not isinstance(point_token_list, list):
                return "Error: point_token_list must be a non-empty list of string tokens."
            if sphere_radius <= 0:
                return "Error: sphere_radius must be positive."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)
            root_comp = design.rootComponent
            results = {}

            # 1) Create or retrieve a TemporaryBRepManager
            temp_brep_mgr = adsk.fusion.TemporaryBRepManager.get()

            # 2) Create a new Base Feature (non-parametric) in the root component
            base_feat = root_comp.features.baseFeatures.add()
            base_feat.startEdit()

            # We'll store references to newly created bodies so we can assign tokens
            # if desired. For example, "sphere_body_tokens": { "tokenForPointA": "bodyToken123", ... }
            sphere_body_tokens = {}

            # 3) Loop over each point token
            for token in point_token_list:
                pt_obj = self.get_hash_obj(token)
                if not pt_obj or not isinstance(pt_obj, adsk.core.Point3D):
                    results[token] = f"Error: token '{token}' is not a valid Point3D."
                    continue

                # Create a sphere for each point using the temporary BRep manager
                try:
                    sphere_body = temp_brep_mgr.createSphere(pt_obj, sphere_radius)
                except Exception as e:
                    results[token] = f"Error creating sphere for token '{token}': {str(e)}"
                    continue

                # Add the BRep body to the Base Feature
                try:
                    new_body = base_feat.bodies.add(sphere_body)
                    # Generate a token if you want to keep track of it
                    # e.g. "Sphere_{x}_{y}_{z}" or something similar
                    sphere_name = f"Sphere_{token}"
                    sphere_body_token = self.set_obj_hash(sphere_name, new_body)
                    sphere_body_tokens[token] = sphere_body_token

                    results[token] = f"Success: Created sphere with radius={sphere_radius} at token '{token}'."
                except Exception as e:
                    results[token] = f"Error adding BRep body to base feature: {str(e)}"

            # 4) Finish editing the Base Feature
            try:
                base_feat.finishEdit()
            except Exception as e:
                results["Error_baseFeature"] = f"Error finishing Base Feature: {str(e)}"

            # 5) Optionally store a token for the entire base feature
            base_feat_name = f"BaseFeature_{len(point_token_list)}Spheres"
            base_feat_token = self.set_obj_hash(base_feat, base_feat_name)

            # Build final JSON
            results["baseFeatureToken"] = base_feat_token
            results["sphere_body_tokens"] = sphere_body_tokens

            return json.dumps(results, indent=2)

        except:
            import traceback
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()



    @ToolCollection.tool_call
    def join_bodies(self, body_token_list: list = None) -> str:
        """
        {
          "name": "join_bodies",
          "description": "Performs a Combine 'Join' operation on all the provided bodies. The first body is the target, and the rest are tools. Returns a JSON result.",
          "parameters": {
            "type": "object",
            "properties": {
              "body_token_list": {
                "type": "array",
                "description": "A list of entity tokens referencing Fusion 360 bodies that will be merged via a Combine feature.",
                "items": { "type": "string" }
              }
            },
            "required": ["body_token_list"],
            "returns": {
              "type": "string",
              "description": "A JSON object with success or error messages."
            }
          }
        }
        """

        try:
            if not body_token_list or not isinstance(body_token_list, list):
                return "Error: body_token_list must be a non-empty list of body tokens."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            design = adsk.fusion.Design.cast(product)
            root_comp = design.rootComponent

            results = {}

            # We need at least two bodies to do a join
            if len(body_token_list) < 2:
                return "Error: At least two bodies are required to perform a join."

            # Retrieve the first body as the target
            target_token = body_token_list[0]
            target_body = self.get_hash_obj(target_token)
            if not target_body or not isinstance(target_body, adsk.fusion.BRepBody):
                return f"Error: The first token '{target_token}' is not a valid Fusion BRepBody."

            # Gather the tool bodies in an ObjectCollection
            tool_bodies = adsk.core.ObjectCollection.create()
            for token in body_token_list[1:]:
                b = self.get_hash_obj(token)
                if not b or not isinstance(b, adsk.fusion.BRepBody):
                    results[token] = f"Error: Token '{token}' is not a valid BRepBody. Skipping."
                    continue
                tool_bodies.add(b)
                results[token] = "Added as a tool body."

            if tool_bodies.count == 0:
                return json.dumps({
                    "Error": "No valid tool bodies found after the first token.",
                    "Details": results
                })

            # Create Combine feature input
            combine_feats = root_comp.features.combineFeatures
            combine_input = combine_feats.createInput(
                target_body,
                tool_bodies
            )
            # Set operation to Join
            combine_input.operation = adsk.fusion.FeatureOperations.JoinFeatureOperation
            # Optionally, you can keep tool bodies if needed
            combine_input.isKeepToolBodies = False

            try:
                combine_feat = combine_feats.add(combine_input)
                results["Operation"] = "Success: Bodies joined into the first body."
            except Exception as e:
                results["Operation"] = f"Error creating Combine feature: {str(e)}"

            return json.dumps(results, indent=2)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()
 


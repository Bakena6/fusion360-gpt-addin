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




class Sketches(ToolCollection):

    #@ToolCollection.tool_call
    def create_spline_in_sketch(self, component_name: str = "comp1", sketch_name: str = "Sketch1", point_list: list = [[0, 0, 0], [1, 1, 0], [2, 0, 0]]):
        """
        {
          "name": "create_spline_in_sketch",
          "description": "Creates a spline in a specified sketch within a specified component in Fusion 360. The spline is defined by an array of points (each an [x, y, z] coordinate in centimeters) that the spline will interpolate through. This function finds the target component and sketch, then constructs a fitted spline based on the provided points.",
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
                  "description": "A list representing an XYZ point (x, y, z) on the sketch plane."
                },
                "description": "An array of points through which the spline will be drawn. The unit for point coordinates is centimeters."
              }
            },
            "required": ["component_name", "sketch_name", "point_list"],
            "returns": {
              "type": "string",
              "description": "A message indicating the success or failure of the spline creation."
            }
          }
        }
        """

        try:
            # If point_list is passed as a JSON string, convert it to a list
            if isinstance(point_list, str):
                point_list = json.loads(point_list)

            # Access the active Fusion 360 design
            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return "Error: No active Fusion 360 design found."

            root_comp = design.rootComponent

            targetComponent, errors = self._find_component_by_name(component_name)
            if not targetComponent:
                return errors

            targetSketch, errors = self._find_sketch_by_name(targetComponent, sketch_name)
            if not targetSketch:
                return errors

            # Create an object collection for the spline points
            points_collection = adsk.core.ObjectCollection.create()
            for pt in point_list:
                if len(pt) != 3:
                    return "Error: Each point in point_list must have three coordinates (x, y, z)."
                point3D = adsk.core.Point3D.create(pt[0], pt[1], pt[2])
                points_collection.add(point3D)

            # Create the spline in the sketch using the fitted spline method
            spline = targetSketch.sketchCurves.sketchFittedSplines.add(points_collection)

            return f"Spline created in sketch '{sketch_name}' of component '{component_name}'."
        except Exception as e:
            return f"Error: Failed to create spline in sketch: {e}"



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

                results["Results"] = f"Success: Extruded {profile_collection.count} profiles by {extrude_distance} (startExtent={start_extent}, taper={taper_angle} with {operation_type}."
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


            #print(f"profile_collection: {profile_collection.count}, {profile_collection}")

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
                revolve_feats.add(rev_input)
                return (f"Revolved profiles in sketch '{sketch.name}' by "
                        f"{revolve_degrees} degrees using {operation_type}.")
            except Exception as e:
                return f"Error creating revolve: {e}"

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


    @ToolCollection.tool_call
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

            sourceComp, errors = self._find_component_by_name(source_component_name)
            if not sourceComp:
                return errors

            targetParentComp, errors = self._find_component_by_name(target_parent_component_name)
            if not targetParentComp:

                return errors

            # Create a new, independent copy of the source component
            transform = adsk.core.Matrix3D.create()  # Identity transform
            new_occurrence = targetParentComp.occurrences.addNewComponentCopy(sourceComp, transform)
            new_comp = new_occurrence.component

            # Rename the newly created component
            new_comp.name = new_component_name

            return f'Successfully created a new, independent copy of "{source_component_name}into "{target_parent_component_name}" named "{new_component_name}".'
        except Exception as e:
            return f'Error: Failed to copy "{source_component_name}" as a new component into "{target_parent_component_name}":\n{e}'

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








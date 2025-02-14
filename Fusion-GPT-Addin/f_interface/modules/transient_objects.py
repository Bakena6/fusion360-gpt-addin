# transient object

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


class TransientObjects(ToolCollection):

    @ToolCollection.tool_call
    def create_point3d_list(self, coords_list: list = [[.5, .5, 0], [1,2,0]]) -> str:
        """
        {
          "name": "create_point3d_list",
          "description": "Creates a set of adsk.core.Point3D objects in memory from the specified list of [x, y, z] coordinates. Returns a JSON mapping each index to the newly created reference token (or name).",
          "parameters": {
            "type": "object",
            "properties": {
              "coords_list": {
                "type": "array",
                "description": "An array of [x, y, z] coordinate triples.",
                "items": {
                  "type": "array",
                  "items": { "type": "number" },
                  "minItems": 3,
                  "maxItems": 3
                }
              }
            },
            "required": ["coords_list"],
            "returns": {
              "type": "string",
              "description": "A JSON object mapping each index in coords_list to the reference token for the newly created Point3D."
            }
          }
        }
        """

        try:
            if not coords_list or not isinstance(coords_list, list):
                return "Error: coords_list must be a non-empty list of [x, y, z] items."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            # If you don't already have a dict for storing references, create one.
            # We'll store the references as self._point_dict: Dict[str, adsk.core.Point3D]
            if not hasattr(self, "_point_dict"):
                self._point_dict = {}

            results = {}
            for i, coords in enumerate(coords_list):
                if not isinstance(coords, list) or len(coords) != 3:
                    results[str(i)] = "Error: invalid [x, y, z] triple."
                    continue

                x, y, z = coords
                # Create the Point3D object
                p3d = adsk.core.Point3D.create(x, y, z)

                p3d_name = f"Point3D__{i}_{x}_{y}_{z}"
                p3d_entity_token = self.set_obj_hash(p3d, p3d_name)

                # Return the token for the user
                results[p3d_entity_token] = f"Success: Created new 'Point3D' with token '{p3d_entity_token}' at {coords}"

            return json.dumps(results)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def create_matrix3d_list(self, matrix_list: list = [[
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0]]) -> str:
        """
        {
          "name": "create_matrix3d_list",
          "description": "Creates a set of adsk.core.Matrix3D objects from an array of 16-float arrays (row-major). Returns a JSON mapping each new matrix's entity token to a success message.",
          "parameters": {
            "type": "object",
            "properties": {
              "matrix_list": {
                "type": "array",
                "description": "An array of 16-float arrays representing row-major 4x4 transforms. Example: [[1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1], [...]]",
                "items": {
                  "type": "array",
                  "items": { "type": "number" },
                  "minItems": 16,
                  "maxItems": 16
                }
              }
            },
            "required": ["matrix_list"],
            "returns": {
              "type": "string",
              "description": "A JSON object mapping each new Matrix3D's token to a success or error message."
            }
          }
        }
        """

        try:
            if not matrix_list or not isinstance(matrix_list, list):
                return "Error: matrix_list must be a non-empty list of 16-float arrays."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            results = {}

            for i, mat_vals in enumerate(matrix_list):
                # Validate input shape
                if not isinstance(mat_vals, list) or len(mat_vals) != 16:
                    results[f"Index_{i}"] = "Error: must provide exactly 16 floats for Matrix3D."
                    continue

                try:
                    m3d = adsk.core.Matrix3D.create()
                    m3d.setWithArray(mat_vals)
                    # Generate a name for referencing
                    mat_name = f"Matrix3D_{i}_{mat_vals}"
                    mat_token = self.set_obj_hash(m3d, mat_name)

                    results[mat_token] = f"Success: Created new 'Matrix3D' with token '{mat_token}' at {mat_vals}."
                except Exception as e:
                    results[f"Index_{i}"] = f"Error: {str(e)}"

            return json.dumps(results)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def create_point2d_list(self, coords_list: list = None) -> str:
        """
        {
          "name": "create_point2d_list",
          "description": "Creates adsk.core.Point2D objects from the given list of [x, y] pairs. Returns a JSON mapping tokens to success messages.",
          "parameters": {
            "type": "object",
            "properties": {
              "coords_list": {
                "type": "array",
                "description": "An array of [x, y] pairs for 2D points.",
                "items": {
                  "type": "array",
                  "items": { "type": "number" },
                  "minItems": 2,
                  "maxItems": 2
                }
              }
            },
            "required": ["coords_list"],
            "returns": {
              "type": "string",
              "description": "A JSON object mapping each new Point2D's token to a success or error message."
            }
          }
        }
        """

        try:
            if not coords_list or not isinstance(coords_list, list):
                return "Error: coords_list must be a non-empty list of [x, y] pairs."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            results = {}

            for i, coords in enumerate(coords_list):
                if not isinstance(coords, list) or len(coords) != 2:
                    results[f"Index_{i}"] = "Error: invalid [x, y] pair."
                    continue

                x, y = coords
                try:
                    p2d = adsk.core.Point2D.create(x, y)
                    p2d_name = f"Point2D_{i}_{x}_{y}"
                    p2d_token = self.set_obj_hash(p2d, p2d_name)
                    results[p2d_token] = f"Success: Created new 'Point2D' with token '{p2d_token}' at {coords}"
                except Exception as e:
                    results[f"Index_{i}"] = f"Error: {str(e)}"

            return json.dumps(results)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def create_matrix2d_list(self, matrix_list: list = None) -> str:
        """
        {
          "name": "create_matrix2d_list",
          "description": "Creates a set of adsk.core.Matrix2D objects from an array of 9-float arrays (row-major). Returns a JSON mapping each new matrix token to success or error.",
          "parameters": {
            "type": "object",
            "properties": {
              "matrix_list": {
                "type": "array",
                "description": "An array of 9-float arrays in row-major format for 2D transforms. Example: [[1,0,0, 0,1,0, 0,0,1], [...]]",
                "items": {
                  "type": "array",
                  "items": { "type": "number" },
                  "minItems": 9,
                  "maxItems": 9
                }
              }
            },
            "required": ["matrix_list"],
            "returns": {
              "type": "string",
              "description": "A JSON object mapping each new Matrix2D's token to a success or error message."
            }
          }
        }
        """
        try:
            if not matrix_list or not isinstance(matrix_list, list):
                return "Error: matrix_list must be a non-empty list of 9-float arrays."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            results = {}

            for i, mat_vals in enumerate(matrix_list):
                if not isinstance(mat_vals, list) or len(mat_vals) != 9:
                    results[f"Index_{i}"] = "Error: must provide exactly 9 floats for Matrix2D."
                    continue

                try:
                    m2d = adsk.core.Matrix2D.create()
                    m2d.setWithArray(mat_vals)
                    mat_name = f"Matrix2D_{i}_{mat_vals}"
                    mat_token = self.set_obj_hash(m2d, mat_name)

                    results[mat_token] = f"Success: Created new 'Matrix2D' with token '{mat_token}' at {mat_vals}."
                except Exception as e:
                    results[f"Index_{i}"] = f"Error: {str(e)}"

            return json.dumps(results)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def create_vector3d_list(self, coords_list: list = [[1, 0, 0], [0, 1, 0]]) -> str:
        """
        {
          "name": "create_vector3d_list",
          "description": "Creates a set of adsk.core.Vector3D objects from the specified list of [x, y, z] coordinates. Returns a JSON mapping each index to the newly created reference token (or name).",
          "parameters": {
            "type": "object",
            "properties": {
              "coords_list": {
                "type": "array",
                "description": "An array of [x, y, z] coordinate triples representing vector directions.",
                "items": {
                  "type": "array",
                  "items": { "type": "number" },
                  "minItems": 3,
                  "maxItems": 3
                }
              }
            },
            "required": ["coords_list"],
            "returns": {
              "type": "string",
              "description": "A JSON object mapping each index in coords_list to the reference token for the newly created Vector3D."
            }
          }
        }
        """

        try:
            if not coords_list or not isinstance(coords_list, list):
                return "Error: coords_list must be a non-empty list of [x, y, z] items."

            app = adsk.core.Application.get()
            if not app:
                return "Error: Fusion 360 is not running."

            product = app.activeProduct
            if not product or not isinstance(product, adsk.fusion.Design):
                return "Error: No active Fusion 360 design found."

            # If you don't already have a dict for storing references, create one.
            # We'll store the references as self._vector_dict: Dict[str, adsk.core.Vector3D]
            if not hasattr(self, "_vector_dict"):
                self._vector_dict = {}

            results = {}
            for i, coords in enumerate(coords_list):
                if not isinstance(coords, list) or len(coords) != 3:
                    results[str(i)] = "Error: invalid [x, y, z] triple."
                    continue

                x, y, z = coords
                # Create the Vector3D object
                vec3d = adsk.core.Vector3D.create(x, y, z)
                vec3d_name = f"Vector3D_{i}_{x}_{y}_{z}"
                vec3d_token = self.set_obj_hash(vec3d, vec3d_name)

                # Store a success message for the new reference token
                results[vec3d_token] = f"Success: Created new Vector3D with token '{vec3d_token}' at {coords}"

            return json.dumps(results)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()

    @ToolCollection.tool_call
    def create_object_collection(self, entity_token_list: list = []) -> str:
        """
        {
          "name": "create_object_collection",
          "description": "Creates an adsk.core.ObjectCollection from the given list of entity tokens. Each token should reference a valid Fusion 360 object. Returns a JSON object containing the final collection token and any error messages for invalid tokens.",
          "parameters": {
            "type": "object",
            "properties": {
              "entity_token_list": {
                "type": "array",
                "description": "A list of entity tokens representing Fusion 360 objects to be collected in an ObjectCollection.",
                "items": {
                  "type": "string"
                }
              }
            },
            "required": ["entity_token_list"],
            "returns": {
              "type": "string",
              "description": "A JSON object containing a 'collectionToken' for the new ObjectCollection, plus success or error messages per token."
            }
          }
        }
        """

        try:
            if not entity_token_list or not isinstance(entity_token_list, list):
                return "Error: entity_token_list must be a non-empty list of strings."

            # Create an empty ObjectCollection
            obj_collection = adsk.core.ObjectCollection.create()

            # We'll store the final JSON results in this dictionary
            items = {}
            # Process each token
            for token in entity_token_list:
                # Attempt to get the associated object from your internal hash / store
                obj = self.get_hash_obj(token)
                if not obj:
                    items[token] = f"Error: No object found for token '{token}'."
                    continue

                # Add to the collection
                try:
                    obj_collection.add(obj)
                    object_type = obj.__class__.__name__
                    items[token] = f"Success: '{object_type}' '{token}' object added to collection."
                except Exception as e:
                    items[token] = f"Error adding object token={token} to collection: {str(e)}"

            # Now we create a reference token for the entire ObjectCollection
            # Provide a unique name or ID as you prefer
            collection_name = f"ObjectCollection_{obj.__class__.__name__}_{len(entity_token_list)}_items"

            collection_token = self.set_obj_hash(obj_collection, collection_name)

            results = {
                collection_token: f"Success: ObjectCollection created with entityToken {collection_token}",
                "items": items
            }

            return json.dumps(results)

        except:
            return "Error: An unexpected exception occurred:\n" + traceback.format_exc()


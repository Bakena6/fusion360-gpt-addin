
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
import hashlib
import random
import base64
import functools

#from ... import config
from ...lib import fusion360utils as futil


def print(string):
    """redefine print for fusion env"""
    futil.log(str(string))

print(f"RELOADED: {__name__.split("%2F")[-1]}")


class ToolCollection:
    """
    methods colletion
    """

    # store references to fusion object based on id
    log_results = True
    log_errors = True

    def tool_call(func):
        """
        Wraps fusion interface calls
        """
        # TODO probably a better way to select functions wrapped in this 
        func.__wrapper__ = "tool_call"

        # for retrieving wrapped function kwarg names
        @functools.wraps(func)
        def wrapper(self, *args, **kwds):
            self.app = adsk.core.Application.get()

            print(func.__name__)

            results = func(self, *args, **kwds)

            if isinstance(results, str):
                try:
                    json.loads(results)
                except Exception as e:
                    results = json.dumps({"results": results})

            #if isinstance(results, dict):
            #    results = json.dumps(results)

            if getattr(ToolCollection, "log_results") == True:
                self.print_results(results)

            return results

        return wrapper


    def __init__(self, ent_dict):
        self.methods = self._get_methods()
        self.ent_dict = ent_dict

    def log_print(self, output):
        print(output)

    @classmethod
    def set_class_attr(cls, settings_dict):

        setting_name = settings_dict.get("setting_name")
        setting_val = settings_dict.get("setting_val")

        current_val = getattr(cls, setting_name, None)
        setattr(ToolCollection, setting_name, setting_val)
        print(f"fusion: {setting_name}:  {current_val} => {setting_val}")

    def print_results(self, results):

        if isinstance(results, str):
            try:
                formatted_results = json.dumps(json.loads(results), indent=4)
            except:
                formatted_results = results
        else:
            formatted_results = results

        print(formatted_results)


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

    def hash_string_to_fixed_length(self, input_string: str, length: int = 10) -> str:
        """
        Returns a stable, unique, alphanumeric hash string of the specified length
        for the given input_string. Uses SHA-256, then Base64, removing non-alphanumeric
        characters and truncating/padding as needed.

        :param input_string: The input string to hash.
        :param length: The desired length of the resulting hash (default=10).
        :return: A hash string of the given length (alphanumeric only).
        """
        # 1) Compute SHA-256 hash
        input_string = str(input_string)
        sha_hash = hashlib.sha256(str(input_string).encode('utf-8')).digest()

        # 2) Encode as Base64 (returns a bytes object)
        b64_encoded = base64.b64encode(sha_hash)  # e.g. b'abcd1234=='

        # Convert to ASCII string
        hash_str = b64_encoded.decode('ascii')  # e.g. "abcd1234=="

        # 3) Remove non-alphanumeric characters (like '=', '+', '/')
        hash_str = re.sub(r'[^A-Za-z0-9]', '', hash_str)

        # 4) Truncate or pad to desired length
        # If it's shorter than 'length' after removing symbols (rare), we can pad with '0'.
        if len(hash_str) < length:
            hash_str += '0' * (length - len(hash_str))
        else:
            hash_str = hash_str[:length]

        return hash_str

    def describe_object(self, obj) -> str:
        """
        Accepts any Fusion 360 (or Python) object and returns a JSON-like string
        describing its non-private attributes (properties) and methods. This
        includes both Python-level and C++-backed method descriptors if found.

        :param obj: The object to introspect.
        :return: A JSON string with two arrays: 'properties' and 'methods'.
        """
        try:
            # A list or set of known internal or private names to ignore
            exclude_list = {"cast", "classType", "__init__", "__del__", "this", "thisown", "attributes", "createForAssemblyContext", "convert", "objectType", "isTemporary", "revisionId", "baseFeature", "meshManager", "nativeObject"}

            # We'll gather results in a dictionary
            result_data = {
        #        "objectType": str(obj.__class__.__name__),
                "attributes": [],
                "methods": []
            }

            # Use inspect.getmembers(...) to get all members
            all_members = inspect.getmembers(obj.__class__)

            # For each (name, value) pair, decide if it's a property or method
            for name, value in all_members:
                # Skip private/dunder and anything in exclude_list
                if name.startswith("_") or name in exclude_list:
                    continue

                if callable(value):
                    # It's a method (function or method descriptor)
                    result_data["methods"].append(name)
                else:
                    # It's a property/attribute
                    result_data["attributes"].append(name)

            # Convert to JSON
            return result_data

        except Exception as e:
            return json.dumps({"error": str(e)})

    def set_sub_attr(self, entity: object, attr_path: str, new_val) -> tuple:
        """
        accepts an entity and attribute path, returns the bottom level method
        """

        # seperater between attribute levels
        delimeter = "."
        # if single attribute name passed
        if delimeter not in attr_path:
            attr_parts = [attr_path]
        else:
            attr_parts = attr_path.split(delimeter)
        # updateed each iteration
        target_entity = entity
        # return vals
        errors = None

        processed_path = f"{target_entity.__class__.__name__}"

        # work down through attrs
        n_attrs = len(attr_parts)
        for index, attr_str in enumerate(attr_parts):

            # alwas check has attr in cas attr exists but is None
            attr_exists = hasattr(target_entity, attr_str)

            if attr_exists == False:
                # successfully accessed attributes
                #processed_path += f".{attr_str}"
                errors = ""
                error_msg = f"Object '{processed_path}' of class '{target_entity.__class__.__name__}' has no attribute/method '{attr_str}'"
                avail_attrs = f"'{target_entity.__class__.__name__}' has the following attributes/methods: {self.describe_object(target_entity)}"

                entity_info = f"Object information: {target_entity.__doc__}"
                errors += f"Error: {error_msg}. {avail_attrs} {entity_info}".strip()
                attr = None
                break

            attr = getattr(target_entity, attr_str)
            if attr is None:
                break

            # successfully accessed attributes
            processed_path += f".{attr_str}"
            # set the target entity to the attr, assumes the attr is an object
            if index < n_attrs-1:
                # when not last iteration
                target_entity = attr

        attr_set = setattr(target_entity, attr_str, new_val)

        return attr_set, errors


    def get_sub_attr(self, entity: object, attr_path: str) -> tuple:
        """
        accepts an entity and attribute path, returns the bottom level method
        """

        # seperater between attribute levels
        delimeter = "."

        # if single attribute name passed
        if delimeter not in attr_path:
            attr_parts = [attr_path]
        else:
            attr_parts = attr_path.split(delimeter)

        # updated each iteration
        target_entity = entity

        # return vals
        errors = None

        processed_path = f"{target_entity.__class__.__name__}"
        #print(entity.name)


        # work down through attrs
        n_attrs = len(attr_parts)
        for index, attr_str in enumerate(attr_parts):
            #print(f"{index}, {target_entity} {target_entity.objectType} {attr_str}")

            try:
                # alwas check has attr in cas attr exists but is None
                attr_exists = hasattr(target_entity, attr_str)
            except Exception as e:
                print(entity.name)
                errors = f"Error: get_sub_attr: {e}"
                attr_exists = False
                attr = None
                break

            if attr_exists == False:
                # successfully accessed attributes
                #processed_path += f".{attr_str}"
                errors = ""
                error_msg = f"Object '{processed_path}' of class '{target_entity.__class__.__name__}' has no attribute/method '{attr_str}'"
                avail_attrs = f"'{target_entity.__class__.__name__}' has the following attributes/methods: {self.describe_object(target_entity)}"

                entity_info = f"Object information: {target_entity.__doc__}"
                errors += f"Error: {error_msg}. {avail_attrs} {entity_info}".strip()
                attr = None
                break

            attr = getattr(target_entity, attr_str)
            #if attr is None:
            #    break

            # successfully accessed attributes
            processed_path += f".{attr_str}"
            # set the target entity to the attr, assumes the attr is an object
            if index < n_attrs-1:
                # when not last iteration
                target_entity = attr


        # if object is entity token, make sure we store object reference
        if attr_str == "entityToken" or attr_str == "id":
            attr = self.set_obj_hash(target_entity)


        return attr, errors


    # TODO handle all operation responses
    def object_creation_response(self, response_obj) -> str:
        """
        converts fusion object to json
        """

        attr_list = [
            #"entityToken",
            "name",
            "area",
            "length",
            "xConstructionAxis",
            "yConstructionAxis",
            "zConstructionAxis",
            "xYConstructionPlane",
            "xZConstructionPlane",
            "yZConstructionPlane",
            #"timelineObject",

        ]

        sub_attr_list = [
            "name",
        ]

        # some responses will be iterable
        response_object_list = []

        if isinstance(response_obj, adsk.fusion.ExtrudeFeature):
            for ent in response_obj.bodies:
                response_object_list.append(ent)

        # object arrays
        elif hasattr(response_obj, "item") == True:
            #print(f"response_obj: {response_obj}")
            for ent in response_obj:
            #    print(f" ent: {ent}")

                response_object_list.append(ent)
        else:
            response_object_list.append(response_obj)


        results = []
        for obj in response_object_list:
            ent_dict = {}
            entity_token = self.set_obj_hash(obj)
            ent_dict["entityToken"] = entity_token
            ent_dict["objectType"] = obj.__class__.__name__

            for attr in attr_list:
                val, errors = self.get_sub_attr(obj, attr)
                if val == None:
                    continue

                # TODO find better way to check if fusion object
                elif any([ isinstance(val, attrType) for attrType in [str, int, float, bool]] ) == True:
                    ent_dict[attr] = val

                else:

                    val_dict = {}
                    val_dict["entityToken"] = self.set_obj_hash(val)
                    val_dict["objectType"] = obj.__class__.__name__

                    for sub_attr in sub_attr_list:
                        sub_val, sub_errors = self.get_sub_attr(val, sub_attr)
                        if sub_val:
                            val_dict[sub_attr] = sub_val

                    val = val_dict

                if val:
                    ent_dict[attr] = val


            results.append(ent_dict)



        return results



    def get_comp_str(self, entity):
        # unique id str, not unique when copied
        id_str = getattr(entity, "id", None)
        ent_tok_str = getattr(entity, "entityToken", None)
        # parent cod/element name
        parent_name = entity.parentDesign.parentDocument.name
        token_str = f"{id_str}_{ent_tok_str}_{parent_name}"

        return token_str



    def set_obj_hash(self, entity: object, ref_occ: str= None, length=5):
        """
        adds a Fusion 360 to the hash:object dict
        """
        if isinstance(entity, str):
            raise Exception

        entity_attrs = dir(entity)

        token_str = None
        entity_type = entity.__class__.__name__

        if isinstance(entity, adsk.fusion.Component):
            token_str = self.get_comp_str(entity)

        elif isinstance(entity, adsk.fusion.Occurrence):

            token_str = getattr(entity, "entityToken", None)

        elif isinstance(entity, adsk.fusion.BRepBodies):
            if ref_occ != None:
                comp_token_str = self.get_comp_str(ref_occ.component)
                token_str = f"{entity_type}_{comp_token_str}_{ref_occ.name}"

            elif entity.count != 0:
                body_0_parent_comp = entity.item(0).parentComponent
                parent_comp_token_str = self.get_comp_str(body_0_parent_comp)
                token_str = f"{entity_type}_{parent_comp_token_str}"
            else:
                token_str = f"{entity_type}_{id(entity)}"

        elif hasattr(entity, "entityToken") == True:
            token_str = getattr(entity, "entityToken", None)

        elif hasattr(entity, "id") == True:
            token_str = getattr(entity, "id", None)

        elif hasattr(entity, "name") == True:
            token_str = getattr(entity, "name", None)

        elif isinstance(entity, adsk.core.Point3D):
            token_str = f"{entity.objectType}_{entity.x}_{entity.y}_{entity.z}"

        else:
            token_str = f"{entity_type}_{id(entity)}"



        hash_val = self.hash_string_to_fixed_length(str(token_str), length)
        hash_val = f"{hash_val}"

        # check token exists
        existing_entity = self.ent_dict.get(hash_val)
        if existing_entity:

            # if token refers to different entities
            if existing_entity != entity:
                print("---")
                print_string = f"Token exists: {hash_val}, token_str: {token_str}"
                spacing = " " *  10

                e0_id = id(existing_entity)
                e1_id = id(entity)

                for n, v in {"prev": existing_entity, "new ": entity }.items():

                    class_name = v.__class__.__name__

                    ent_name = getattr(v, "name", None)

                    print_string += f"\n {n}: {class_name}, {ent_name}"

                print(print_string)
                print(f"  e0: {e0_id}, {existing_entity}")
                print(f"  e1: {e1_id}, {entity}")



        self.ent_dict[hash_val] = entity

        return hash_val


    def get_hash_obj(self, hash_val):
        """
        adds a fusion360 to the hash:object dict
        """

        return self.ent_dict.get(hash_val)





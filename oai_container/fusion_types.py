import adsk
import adsk.core
import adsk.fusion
import adsk.cam
import pydoc

import inspect
import importlib
import json
import traceback

#print(dir(adsk.fusion))

#print(dir(adsk.core.Application))
#print(adsk.core.Application)


#print(dir(adsk.core.Application.get().documents))

#print(dir(adsk.fusion.DesignTypes))
#print(adsk.fusion.DesignTypes())

#print(dir(adsk.core.Application))

#print(dir(adsk.fusion))

exclude_list = []

output_list = []





print("------------------")


def object_tree(entity, levels):


    results= {}
    count = 0
    exclude_list = ["Definition", "_",  "ContactSet" , "BoundryFill", 
                    "boxFeature",
                    "Custom",
                    "TriangleMesh",
                    "core",
                    "WebFeature",
                    "SplitBodyFeature",
                    "RuledSurfaceFeature",
                    "Hole",
                    "Trim",
                    "Untrim",
                    "Stitch",
                    "Unstitch",
                    "TemporaryBRepManager",
                    "Thread",
                    "Loft",
                    "Mesh",
                    "Extend",
                    "Draft",
                    "Delete",
                    "Thicken",
                    "UnitsM",
                    "FormFeature",
                    "Flange",
                    "C3MFExportOptions",
                    "BoundaryFillFeature",
                    "fold",
                    "Sweep",
                    "SplitFace",
                    "SmoothConstraint",
                    "ExportOptions",
                    "Replace",
                    "Rib",
                    "Reverse",
                    "OffsetFace",
                    "InputOptions",
                    "Input",
                    "Motion"

                    ]

    for attr_name in dir(entity):

        if any([t in attr_name for t in exclude_list]):
            #print(f" excluding: {attr_name}")
            continue


        # skip internal methods
        if (attr_name[0] == "_") or (attr_name in exclude_list):
            continue

        try:
            attr_val = getattr(entity, attr_name)

        except Exception as e:
            print(f"Error: attr_name: {attr_name} occurred:\n" + traceback.format_exc())
            continue

        docs_raw = pydoc.render_doc(attr_val)
        doc_str = pydoc.plain(docs_raw).replace("|", " ")

        print(attr_name, len( doc_str))

        output_list.append(doc_str)

        continue


    return results


#object_tree(adsk.fusion, 0)

output_str = "".join(output_list)
output_str = output_str.replace("----------------------------------------------------------------------", "--------")
output_str = output_str.replace("    ", "  ")
output_str = output_str.replace("""__dict__
    dictionary for instance variables (if defined)""", "")

output_str = output_str.replace("""__weakref__
    list of weak references to the object (if defined)""", "")


output_str = output_str.replace("""__init__(self)
    Initialize self.  See help(type(self)) for accurate signature.""", "")


#print(pydoc.render_doc(pydoc.writedocs))
#print(output_str)

#output_str = pydoc.render_doc(adsk.fusion)
# Render the raw documentation with potential control/backspace chars
#docs_raw = pydoc.render_doc(adsk.fusion)

# Strip out formatting so repeated characters (backspaces) go away

output_path = "Fusion_360_documentation.txt"


#with open(output_path, "w", encoding="utf-8") as f:
#    f.write(output_str)



#@ToolCollection.tool_call
def list_fusion_methods(class_names: list = ["Sketch"]) -> str:
    """
    {
      "name": "list_fusion_methods",
      "description": "Accepts a list of Fusion 360 class names (with or without full path) and returns a JSON object mapping each class name to an array of method names. If the class cannot be found or has no methods, an error is returned or an empty list is provided.",
      "parameters": {
        "type": "object",
        "properties": {
          "class_names": {
            "type": "array",
            "description": "List of classes to introspect. E.g. ['Sketch', 'adsk.fusion.ExtrudeFeature']. If no module is specified, tries adsk.fusion then adsk.core.",
            "items": { "type": "string" }
          }
        },
        "required": ["class_names"],
        "returns": {
          "type": "string",
          "description": "A JSON object mapping each requested class name to an array of method names or an error string."
        }
      }
    }
    """

    try:
        if not class_names or not isinstance(class_names, list):
            return json.dumps({"error": "class_names must be a non-empty list of strings"})

        def import_class_from_path(path: str):
            """
            Attempt to import something like 'adsk.fusion.Sketch'.
            Returns (cls, None) if successful, or (None, errorString) if failed.
            """
            tokens = path.split(".")
            if len(tokens) < 2:
                return None, f"Invalid class path: '{path}'."
            mod_str = ".".join(tokens[:-1])
            cls_str = tokens[-1]
            try:
                mod = importlib.import_module(mod_str)
            except ModuleNotFoundError:
                return None, f"Could not import module '{mod_str}'."
            cls = getattr(mod, cls_str, None)
            if cls is None:
                return None, f"Class '{cls_str}' not found in '{mod_str}'."
            return cls, None

        # We'll skip private/dunder methods, or internal known items
        exclude_list = ["cast", "classType", "__init__", "__del__"]

        def gather_method_names(cls):
            """
            Collect the names of all Python-level methods and method descriptors,
            skipping anything private (leading underscore) or in exclude_list.
            """
            method_names = set()

            # 1) Python-level methods
            py_methods = inspect.getmembers(cls, predicate=inspect.isfunction)
            for name, _ in py_methods:
                if name.startswith("_") or name in exclude_list:
                    continue
                method_names.add(name)

            # 2) C++-backed method descriptors (common in Fusion API)
            desc_methods = inspect.getmembers(cls, predicate=inspect.ismethoddescriptor)
            for name, _ in desc_methods:
                if name.startswith("_") or name in exclude_list:
                    continue
                # If not already added, store it
                if name not in method_names:
                    method_names.add(name)

            return sorted(method_names)

        def get_class_methods(class_name: str):
            """
            Resolves the class, returning a sorted list of method names or an error string.
            """
            if "." in class_name:
                # Assume it's a fully qualified path, e.g. "adsk.fusion.Sketch"
                cls, err = import_class_from_path(class_name)
                if err:
                    return err
                return gather_method_names(cls)
            else:
                # Try adsk.fusion.CLASS, then adsk.core.CLASS
                fusion_path = f"adsk.fusion.{class_name}"
                cls_fus, err_fus = import_class_from_path(fusion_path)
                if not err_fus and cls_fus:
                    return gather_method_names(cls_fus)

                core_path = f"adsk.core.{class_name}"
                cls_core, err_core = import_class_from_path(core_path)
                if not err_core and cls_core:
                    return gather_method_names(cls_core)

                # If both fail, return an error string
                return f"Could not find class '{class_name}' in adsk.fusion or adsk.core."

        # Final results
        results = {}
        for class_name in class_names:
            method_data = get_class_methods(class_name)
            if isinstance(method_data, str):
                # It's an error string
                results[class_name] = {"error": method_data}
            else:
                # It's a list of method names
                results[class_name] = method_data

        return json.dumps(results, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})






classes = list_fusion_methods([ "SketchArcs",
		"SketchCircles",
		"SketchConicCurves",
		"SketchControlPointSplines",
		"SketchEllipses",
		"SketchEllipticalArcs",
		"SketchFittedSplines",
		"SketchFixedSplines",
		"SketchLines"
])
print( classes)




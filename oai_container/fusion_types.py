import adsk
import adsk.core
import adsk.fusion
import adsk.cam
import pydoc

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


object
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


object_tree(adsk.fusion, 0)

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


with open(output_path, "w", encoding="utf-8") as f:
    f.write(output_str)












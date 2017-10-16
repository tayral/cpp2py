# Generated automatically using the command :
# ${W.shell_command}
from cpp2py.wrap_generator import *

# The module
module = module_(full_name = "${W.modulename}", doc = "${doc.replace_latex(W.moduledoc)}", app_name = "${W.appname}")

# Imports
%for mod in import_list :
import ${mod}
%endfor

# Add here all includes 
module.add_include("${W.filename.replace("../c++/",'')}")

# Add here anything to add in the C++ code at the start, e.g. namespace using
module.add_preamble("""
%for conv in converters_list :
#include <${conv}>
%endfor
%for ns in using_list :
using namespace ${ns};
%endfor
%if param_cls_list :
#include "${W.modulename.rsplit('.',1)[-1]}_converters.hxx"
%endif
""")
##
%for c in W.all_classes_gen():
# The class ${c.spelling}
c = class_(
        py_type = "${util.deduce_normalized_python_class_name(c.spelling)}",  # name of the python class
        c_type = "${c.spelling}",   # name of the C++ class
        doc = """${doc.make_doc(c)}""",   # doc of the C++ class
)
<%
  methods, proplist = W.separate_method_and_properties(c)
%>
%for m in CL.get_members(c, False, CL.is_public) :
c.add_member(c_name = "${m.spelling}",
             c_type = "${m.type.spelling}",
             read_only= ${W.members_read_only},
             doc = """${doc.make_doc(m)}""")

%endfor
##
%for m in CL.get_constructors(c, W.keep_fnt):
c.add_constructor("""${W.make_signature_for_desc(m, True)}""", doc = """${doc.make_doc(m)}""")

%endfor
##
%for m in methods:
c.add_method("""${W.make_signature_for_desc(m)}""",
             %if m.is_static_method() :
             is_static = True,
             %endif
             doc = """${doc.make_doc(m)}""")

%endfor
##
%for p in proplist:
c.add_property(name = "${p.name}",
               getter = cfunction("${W.make_signature_for_desc(p.getter)}"),
               %if p.setter :
               setter = cfunction("${W.make_signature_for_desc(p.setter)}"),
               %endif
               doc = """${p.doc}""")

%endfor
##
module.add_class(c)

%endfor
##
%for f in W.all_functions_gen():
module.add_function ("${W.make_signature_for_desc(f)}", doc = """${doc.make_doc(f)}""")

%endfor
##
module.generate_code()

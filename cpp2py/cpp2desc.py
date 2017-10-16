import os, re, sys, itertools
from mako.template import Template

import cpp2py.clang_parser as CL
import util, doc, dependency_analyzer, converters

class Cpp2Desc: 
    """ """
    def __init__(self, filename, namespaces=(), classes= (), namespace_to_factor= (), appname= '', 
                 modulename = '', moduledoc ='', use_properties = False, members_read_only = True,  converters = (),
                 compiler_options=None, includes= None, libclang_location = None, shell_command = '', parse_all_comments = True):
        """
           Parse the file at construction
           
           Parameters
           -----------

           filename : string
                      Name of the file to parse
           
           namespaces : list of string 
                      Restrict the generation to the given namespaces.
           
           classes : list of string
                      Restrict the generation to the given classes.
           
           appname  : string
                      Name of the application
           
           modulename : string
                      Name of the module
           
           moduledoc : string
                       Documentation of the module

           shell_command : string
                           script command that was called (to regenerate the desc file)

           use_properties : Boolean
                            Transform method with no args into property

           members_read_only : Boolean
                               The members are wrapped "read only"

           includes         : string, optional
                      Additional includes to add (-I xxx) for clang
           
           compiler_options : string, optional 
                      Additional option for clang compiler
           
           libclang_location : string, optional
                      Absolute path to libclang. By default, the detected one.
        """
        for x in ['filename', 'namespaces', 'classes', 'namespace_to_factor', 'appname', 'modulename', 'moduledoc', 
                  'use_properties', 'members_read_only', 'shell_command']:
            setattr(self, x, locals()[x])
        self.DE = dependency_analyzer.DependencyAnalyzer(converters)
        # parse the file
        self.root = CL.parse(filename, compiler_options, includes, libclang_location, parse_all_comments)

    # ---------- Generate the AST nodes for every classes, functions, functions and methods
    
    def keep_ns(self, n):
        if n.location.file.name != self.filename: return False
        return len(self.namespaces) == 0 or n.spelling in self.namespaces
    
    def keep_cls(self, c):
        if c.location.file.name != self.filename: return False
        if self.classes : return c.spelling in self.classes
        ign = len(self.namespaces)>0 and c.type.get_canonical().spelling.rsplit('::',1) in self.namespaces
        return not(ign or CL.is_template(c) or ("ignore_in_python" in CL.get_annotations(c)))
    
    def keep_fnt(self, f) :
        ign = f.spelling.startswith('operator') or f.spelling in ['begin','end']
        return self.keep_cls(f) and not(ign)
    
    def all_functions_gen(self):
        """Generates all the AST nodes of classes (mode = 'C') or functions (mode = 'F')"""
        return CL.get_functions(self.root, self.keep_fnt, traverse_namespaces = True, keep_ns = self.keep_ns)

    def all_classes_gen(self):
        """Generates all the AST nodes of classes (mode = 'C') or functions (mode = 'F')"""
        return CL.get_classes(self.root, self.keep_cls, traverse_namespaces = True, keep_ns = self.keep_ns)

    def get_all_functions_and_methods(self):
        """ AST nodes for every function, class methods and constructors"""
        for f in self.all_functions_gen(): 
            yield f
        for c in self.all_classes_gen(): 
            for m in CL.get_methods(c):
                yield m
            for m in CL.get_constructors(c):
                yield m

    def get_all_param_classes(self):
        """ yields all param classes """
        for f in self.get_all_functions_and_methods():
            r = util.get_decl_param_class(f)
            if r : 
                yield r

    def get_all_params_ret_type(self, param_cls_list):
        """Yields every parameters and return type of every methods and functions"""
       
        for f in self.all_functions_gen():
            yield getattr(f, 'result_type', None)
            for p in CL.get_params(f) : 
                yield p.type

        for x in itertools.chain(param_cls_list, self.all_classes_gen()): 
            for m in CL.get_members(x, False): # False : no inherited
                yield m.type
            for m in itertools.chain(CL.get_constructors(x), CL.get_methods(x)): 
                yield getattr(m, 'result_type', None)
                for p in CL.get_params(m) : 
                    yield p.type

    def get_public_methods(self, c):
        """
        Parameters
        -----------

        c:  AST node
            a cursor to a class
        
        Returns
        --------
        A list of cursors to the methods
        return : a tuple (proplist, methodlist) where proplist : a list of property_  and methodlist : the others methods
        """ 
        keep = lambda m : CL.is_public(m) and not m.spelling.startswith('operator')
        return CL.get_methods(c, True, keep)
        
    def separate_method_and_properties(self, c):
        """
        Treatment of properties

        Parameters
        -----------

        method_list : a generator of the methods to treat
        
        Returns
        --------
          Tuple (proplist, methodlist) where
                  proplist : a list of property_
                  methodlist : the others methods
        """ 

        method_list = list(self.get_public_methods(c)) # MUST be a list, or the generator will be exhausted later in mlist = ...
        if not self.use_properties : return method_list, ()

        class property_:
            def __init__ (self, **kw) :
                self.__dict__.update(kw)

        def maybe_prop(m):
            return len(list(CL.get_params(m))) == 0 and not m.is_static_method()

        plist1 = [m for m in method_list if maybe_prop(m)]
        mlist =  [m for m in method_list if not maybe_prop(m)]
        plist = []

        for m in plist1:
            n, set_m = m.spelling, None
            if n.startswith('set_') : continue # do nothing, will be treated with the get_
            if n.startswith('get_') : 
                # treat the corresponding setter 
                n = n[4:] 
                set_m = next( (m for m in plist if m.spelling == 'set_' + n), None)
                if set_m : 
                    p = list(CL.get_params(set_m)) 
                    if set_m.result_type.spelling == "void" and len(p) ==1 :
                        if not util.decay(p[0].spelling) == m.result_type.spelling :
                            print "Warning :"
                            print "   in get_%s/set_%s" %(X,X)
                            print "     The type taken from set_%s is not the return type of get_%s"%(X,X)
                            print "    Expected ",m.result_type.spelling
                            print "    Got ", decay(p[0].spelling)
                            print "     I am not adding the setter to the property"
                            set_m = None
            print "Transforming to property : ", m.spelling, set_m.spelling if set_m else ''
            plist.append(property_(name= n, doc = doc.make_doc(m), getter = m, setter = set_m))

        return mlist, plist
  
    def make_signature_for_desc(self, f, is_constructor = False):
        """Given a node of a function/methods, it makes the signature for desc file"""
        # first format the arguments
        def cls(t) :
            tname = util.decay(t)
            tname = tname.replace(' ','')
            for ns in self.namespace_to_factor : 
                tname = re.sub(ns + '::','',tname)
            return tname
        
        if util.use_parameter_class(f) : 
            r = '**%s'%cls(CL.get_params(f).next().type.spelling)
        else:
            plist = [ (cls(p.type.spelling), p.spelling, CL.get_param_default_value(p)) for p in CL.get_params(f)]
            r = ', '.join("%s %s"%(t, n) + (" = %s"%d.replace('"','\\"') if d else "") for t, n, d  in plist ) 

        if is_constructor:
            return "(%s)"%r
        else :
            return ("%s %s (%s)"%(cls(f.result_type.spelling), f.spelling, r)).strip()

    def generate_desc_file(self, output_filename, verbose  = True):
        """ Makes the desc file"""
         
        # First treat the parameter class if any (classes passed by dictionnary that MUST be converted)
        param_cls_list = list(self.get_all_param_classes())
        if param_cls_list : 
            if verbose : 
                print "Generating Python-C++ converters for : "
                for c in param_cls_list:
                    print "   ", c.spelling
            # CXX file
            open("%s_converters.hxx"%self.modulename, "w").write('\n'.join(converters.make_converter_cxx(c) for c in param_cls_list))
            # Doc
            open('parameters.rst', 'w').write('\n'.join(doc.doc_param_dict_format(CL.get_members(c, True)) for c in param_cls_list))

        # analyse the modules and converters that need to be added
        print "Analysing dependencies"
        types_being_wrapped_or_converted = param_cls_list + list(self.all_classes_gen())
        import_list, converters_list = self.DE(self.get_all_params_ret_type(param_cls_list), types_being_wrapped_or_converted)
    
        # Render mako
        print "Generating " + output_filename
        tpl = Template(filename= util.script_path() + '/mako/desc.py', strict_undefined = True)
        rendered = tpl.render(W = self, CL = CL, doc = doc, util = util,  
                              param_cls_list = param_cls_list, 
                              import_list = import_list, converters_list = converters_list, using_list = self.namespace_to_factor)
        open(output_filename, "w").write(util.clean_end_and_while_char(rendered))

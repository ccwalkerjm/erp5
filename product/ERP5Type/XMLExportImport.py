##############################################################################
#
# Copyright (c) 2002-2003 Nexedi SARL and Contributors. All Rights Reserved.
#                    Sebastien Robin <seb@nexedi.com>
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

from Acquisition import aq_base, aq_inner

from cStringIO import StringIO
from email.MIMEBase import MIMEBase
from email import Encoders
from pickle import Pickler, EMPTY_DICT, MARK, DICT, PyStringMap, DictionaryType
from xml.sax.saxutils import escape, unescape
from lxml import etree
from lxml.etree import Element, SubElement
from xml.marshal.generic import dumps as marshaler
from OFS.Image import Pdata
from zLOG import LOG
from base64 import standard_b64encode

class OrderedPickler(Pickler):
    
    dispatch = Pickler.dispatch.copy()
    
    def save_dict(self, obj):
        write = self.write
        if self.bin:
            write(EMPTY_DICT)
        else:   # proto 0 -- can't use EMPTY_DICT
            write(MARK + DICT)
        self.memoize(obj)
        key_list = obj.keys()
        key_list.sort() # Order keys
        obj_items = map(lambda x: (x, obj[x]), key_list) # XXX Make it lazy in the future
        self._batch_setitems(obj_items)
    
    dispatch[DictionaryType] = save_dict
    if not PyStringMap is None:
        dispatch[PyStringMap] = save_dict        

# ERP5 specific pickle function - produces ordered pickles
def dumps(obj, protocol=None, bin=None):
    file = StringIO()
    OrderedPickler(file, protocol, bin).dump(obj)
    return file.getvalue()

def Base_asXML(object, root=None):
  """
      Generate an xml text corresponding to the content of this object
  """
  self = object
  return_as_object = True
  if root is None:
    return_as_object = False
    root = Element('erp5')
  #LOG('asXML',0,'Working on: %s' % str(self.getPhysicalPath()))

  object = SubElement(root, 'object',
                      attrib=dict(id=self.getId(), portal_type=self.getPortalType()))

  # We have to find every property
  for prop_id in self.propertyIds():
    # In most case, we should not synchronize acquired properties
    if prop_id not in ('uid', 'workflow_history', 'id', 'portal_type',):
      value = self.getProperty(prop_id)
      if value is None:
        prop_type = 'None'
      else:
        prop_type = self.getPropertyType(prop_id)
      sub_object = SubElement(object, prop_id, attrib=dict(type=prop_type))
      if prop_type in ('object',):
        # We may have very long lines, so we should split
        value = aq_base(value)
        value = dumps(value)
        sub_object.text = standard_b64encode(value)
      elif prop_type in ('data',):
        # Create blocks to represent data
        # <data><block>ZERD</block><block>OEJJM</block></data>
        size_block = 60
        if isinstance(value, str):
          iterator_block = 0
          for index in xrange(0, len(value), size_block):
            content = value[index:index + size_block]
            data_encoded = standard_b64encode(content)
            block = SubElement(sub_object, 'block_data', num=str(iterator_block))
            block.text = data_encoded
            iterator_block += 1
        else: 
          raise "XMLExportImport failed, the data is undefined"
      elif prop_type in ('lines', 'tokens',):
        # Use CDATA node to not be taken into account by erp5diff 
        value = [word.decode('utf-8').encode('ascii','xmlcharrefreplace')\
            for word in value]
        sub_object.text = etree.CDATA(marshaler(value))
      elif prop_type in ('text', 'string',):
        sub_object.text = unicode(escape(value), 'utf-8')
      elif prop_type != 'None':
        sub_object.text = str(value)

  # We have to describe the workflow history
  if getattr(self, 'workflow_history', None) is not None:
    workflow_list = self.workflow_history
    workflow_list_keys = workflow_list.keys()
    workflow_list_keys.sort() # Make sure it is sorted

    for workflow_id in workflow_list_keys:
      for workflow_action in workflow_list[workflow_id]:
        workflow_node = SubElement(object, 'workflow_action',
                                   attrib=dict(id=workflow_id))
        worfklow_variable_list = workflow_action.keys()
        worfklow_variable_list.sort()
        for workflow_variable in worfklow_variable_list:
          variable_type = "string" # Somewhat bad, should find a better way
          if workflow_variable.find('time') >= 0:
            variable_type = "date"
          if workflow_variable.find('language_revs') >= 0: # XXX specific to cps
            variable_type = "dict"
          variable_node = SubElement(workflow_node, workflow_variable,
                                     attrib=dict(type=variable_type))
          variable_node_text = str(workflow_action[workflow_variable])
          variable_node.text = unicode(variable_node_text, 'utf-8')

  # We should now describe security settings
  for user_role in self.get_local_roles():
    local_role_node = SubElement(object, 'local_role',
                                 attrib=dict(id=user_role[0], type='tokens'))
    #convert local_roles in string because marshaler can't do it
    role_list = []
    for role in user_role[1]:
      if isinstance(role, unicode):
        role = role.encode('utf-8')
      role_list.append(role)
    local_role_node.text = etree.CDATA(marshaler(tuple(role_list)))
  if getattr(self, 'get_local_permissions', None) is not None:
    for user_permission in self.get_local_permissions():
      local_permission_node = SubElement(object, 'local_permission',
                              attrib=dict(id=user_permission[0], type='tokens'))
      local_permission_node.text = etree.CDATA(marshaler(user_permission[1]))
  # Sometimes theres is roles specified for groups, like with CPS
  if getattr(self, 'get_local_group_roles', None) is not None:
    for group_role in self.get_local_group_roles():
      local_group_node = SubElement(object, 'local_group',
                                    attrib=dict(id=group_role[0], type='tokens'))
      local_group_node.text = etree.CDATA(marshaler(group_role[1]))
  if return_as_object:
    return root
  return etree.tostring(root, encoding='utf-8',
                        xml_declaration=True, pretty_print=True)

def Folder_asXML(object, omit_xml_declaration=True, root=None):
  """
      Generate an xml text corresponding to the content of this object
  """
  xml_declaration = not omit_xml_declaration
  from Products.ERP5Type.Base import Base
  self = object
  if root is None:
    root = Element('erp5')
  Base_asXML(self, root=root)
  root_node = root.find('object')
  # Make sure the list of sub objects is ordered
  id_list = sorted(self.objectIds())
  # Append to the xml the xml of subobjects
  for id in id_list:
    o = self._getOb(id)
    if issubclass(o.__class__, Base):
      o.asXML(root=root_node)

  return etree.tostring(root, encoding='utf-8',
                        xml_declaration=xml_declaration, pretty_print=True)

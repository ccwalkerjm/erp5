##############################################################################
#
# Copyright (c) 2002 Nexedi SARL and Contributors. All Rights Reserved.
#                    Jean-Paul Smets-Solanes <jp@nexedi.com>
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

from Globals import InitializeClass
from AccessControl import ClassSecurityInfo
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.WorkflowCore import WorkflowMethod

from Products.ERP5Type import Permissions, PropertySheet, Constraint, Interface
from Products.ERP5.Core import MetaNode, MetaResource

from Products.ERP5.Document.Movement import Movement

from zLOG import LOG

# XXX Do we need to create groups ? (ie. confirm group include confirmed, getting_ready and ready

parent_to_movement_simulation_state = {
  'cancelled'        : 'cancelled',
  'draft'            : 'draft',
  'auto_planned'     : 'auto_planned',
  'planned'          : 'planned',
  'ordered'          : 'planned',
  'confirmed'        : 'planned',
  'getting_ready'    : 'planned',
  'ready'            : 'planned',
  'started'          : 'planned',
  'stopped'          : 'planned',
  'delivered'        : 'planned',
  'invoiced'         : 'planned',
}

class SimulationMovement(Movement):
  """
      Simulation movements belong to a simulation workflow which includes
      the following steps

      - planned

      - ordered

      - confirmed (the movement is now confirmed in qty or date)

      - started (the movement has started)

      - stopped (the movement is now finished)

      - delivered (the movement is now archived in a delivery)

      The simulation worklow uses some variables, which are
      set by the template

      - is_order_required

      - is_delivery_required


      XX
      - is_problem_checking_required ?

      Other flag
      (forzen flag)

      NEW: we do not use DCWorklow so that the simulation process
      can be as much as possible independent of a Zope / CMF implementation.
  """
  meta_type = 'ERP5 Simulation Movement'
  portal_type = 'Simulation Movement'
  add_permission = Permissions.AddPortalContent
  isPortalContent = 1
  isRADContent = 1
  isMovement = 1

  # Declarative security
  security = ClassSecurityInfo()
  security.declareObjectProtected(Permissions.View)

  # Declarative interfaces
  __implements__ = ( Interface.Variated, )

  # Declarative properties
  property_sheets = ( PropertySheet.Base
                    , PropertySheet.SimpleItem
                    , PropertySheet.CategoryCore
                    , PropertySheet.Amount
                    , PropertySheet.Task
                    , PropertySheet.Arrow
                    , PropertySheet.Movement
                    , PropertySheet.Simulation
                    )

  # Factory Type Information
  factory_type_information = \
      {    'id'             : portal_type
         , 'meta_type'      : meta_type
         , 'description'    : """\
An Organisation object holds the information about
an organisation (ex. a division in a company, a company,
a service in a public administration)."""
         , 'icon'           : 'segment_icon.gif'
         , 'product'        : 'ERP5'
         , 'factory'        : 'addSimulationMovement'
         , 'immediate_view' : 'predicate_view'
         , 'actions'        :
        ( { 'id'            : 'view'
          , 'name'          : 'View'
          , 'category'      : 'object_view'
          , 'action'        : 'predicate_view'
          , 'permissions'   : (
              Permissions.View, )
          }
        , { 'id'            : 'print'
          , 'name'          : 'Print'
          , 'category'      : 'object_print'
          , 'action'        : 'segment_print'
          , 'permissions'   : (
              Permissions.View, )
          }
        , { 'id'            : 'metadata'
          , 'name'          : 'Metadata'
          , 'category'      : 'object_view'
          , 'action'        : 'metadata_edit'
          , 'permissions'   : (
              Permissions.View, )
          }
        , { 'id'            : 'translate'
          , 'name'          : 'Translate'
          , 'category'      : 'object_action'
          , 'action'        : 'segment_view'
          , 'permissions'   : (
              Permissions.TranslateContent, )
          }
        )
      }
  # Price should be acquired
  security.declareProtected(Permissions.AccessContentsInformation, 'getPrice')
  def getPrice(self, context=None, REQUEST=None, **kw):
    """
    """
    return self._baseGetPrice() # Call the price method

  security.declareProtected(Permissions.AccessContentsInformation, 'getCausalityState')
  def getCausalityState(self):
    """
      Returns the current state in causality
    """
    return getattr(self, 'causality_state', 'solved')

  def setCausalityState(self, value):
    """
      Change causality state
    """
    self.causality_state = value

  security.declareProtected(Permissions.AccessContentsInformation, 'getSimulationState')
  def getSimulationState(self, id_only=1):
    """
      Returns the current state in simulation

      Inherit from order or delivery or parent (but use a conversion table to make
      orders planned when parent is confirmed)

      XXX: movements in zero stock rule can not acquire simulation state
    """
    delivery = self.getDeliveryValue()
    if delivery is not None:
      return delivery.getSimulationState()
    order = self.getOrderValue()
    if order is not None:
      return order.getSimulationState()
    try:
      parent_state = self.aq_parent.getSimulationState()
      return parent_to_movement_simulation_state[parent_state]
    except:
      LOG('ERP5 WARNING:',100, 'Could not acquire getSimulationState on %s' % self.getRelativeUrl())
      return None

  # Acounting
  security.declareProtected(Permissions.AccessContentsInformation, 'isAccountable')
  def isAccountable(self):
    """
      Returns 1 if this needs to be accounted
      Only account movements which are not associated to a delivery
      Whenever delivery is there, delivery has priority
    """
    return (self.getDeliveryValue() is None)

  # Ordering / Delivering
  security.declareProtected(Permissions.AccessContentsInformation, 'requiresOrder')
  def requiresOrder(self):
    """
      Returns 1 if this needs to be ordered
    """
    if isOrderable():
      return len(self.getCategoryMembership('order')) is 0
    else:
      return 0

  security.declareProtected(Permissions.AccessContentsInformation, 'requiresDelivery')
  def requiresDelivery(self):
    """
      Returns 1 if this needs to be accounted
    """
    if isDeliverable():
      return len(self.getCategoryMembership('delivery')) is 0
    else:
      return 0


  #######################################################
  # Causality Workflow Methods

  security.declareProtected(Permissions.ModifyPortalContent, 'expand')
  def expand(self, **kw):
    """
      -> new status : expanded

      Parses all existing applied rules and make sure they apply.
      Checks other possible rules and starts expansion process
      (instanciates rule and calls expand on rule)

      Only movements which applied rule parent is expanded can
      be expanded.
    """
    #LOG('In simulation expand',0, str(self.id))
    self.reindexObject()
    if self.getCausalityState() is 'expanded':
      # Reexpand
      for my_applied_rule in self.objectValues():
        my_applied_rule.expand(**kw)
    else:
      portal_rules = getToolByName(self, 'portal_rules')
      # Parse each applied rule and test if it applied
      #for applied_rule in self.objectValues():
      #  if not applied_rule.test():
      #    # delete
      # Parse each rule and test if it applies
      for rule in portal_rules.objectValues():
        if rule.test(self):
          my_applied_rule = rule.constructNewAppliedRule(self)
          my_applied_rule.expand()
      # Set to expanded
      self.setCausalityState('expanded')

  #expand = WorkflowMethod(expand) USELESS NOW

  security.declareProtected(Permissions.ModifyPortalContent, 'solve')
  def solve(self, solver, new_target=None):
    """
       Makes the movement expandable again

       -> new status -> solved

       Once a movement has been updated with consistent
       target and planned values, it is marked as solved
       and can therefore be expanded again
    """
    self.portal_simulation.applyTargetSolver(self, solver, new_target=new_target)
    self.setCausalityState('solved')

  #solve = WorkflowMethod(solve) USELESS NOW

  security.declareProtected(Permissions.ModifyPortalContent, 'diverge')
  def diverge(self):
    """
       -> new status -> diverged

       Movements which diverge can not be expanded
    """
    self.setCausalityState('diverged')

  #diverge = WorkflowMethod(diverge) USELESS NOW

  # isDivergent is defined in movement

  # Optimized Reindexing
  security.declareProtected(Permissions.AccessContentsInformation, 'getMovementIndex')
  def getMovementIndex(self):
    """
      Returns a list of indexable movements
    """
    result = [ { 'uid'                            : self.getUid(),
                 'id'                             : self.getId(),
                 'portal_type'                    : self.getPortalType(),
                 'url'                            : self.getUrl(),
                 'relative_url'                   : self.getRelativeUrl(),
                 'parent_uid'                     : self.getParentUid(),
                 'simulation_state'               : self.getSimulationState(),
                 'order_uid'                      : self.getOrderUid(),
                 'explanation_uid'                : self.getExplanationUid(),
                 'delivery_uid'                   : self.getDeliveryUid(),
                 'source_uid'                     : self.getSourceUid(),
                 'destination_uid'                : self.getDestinationUid(),
                 'source_section_uid'             : self.getSourceSectionUid(),
                 'destination_section_uid'        : self.getDestinationSectionUid(),
                 'resource_uid'                   : self.getResourceUid(),
                 'quantity'                       : self.getNetConvertedQuantity(),
                 'start_date'                     : self.getStartDate(),
                 'stop_date'                      : self.getStopDate(),
                 'target_quantity'                : self.getNetConvertedTargetQuantity(),
                 'target_start_date'              : self.getTargetStartDate(),
                 'target_stop_date'               : self.getTargetStopDate(),
                 'price'                          : self.getPrice(),
                 'total_price'                    : self.getTotalPrice(),
                 'target_total_price'             : self.getTargetTotalPrice(),
                 'has_cell_content'               : 0,
                 'accountable'                    : self.isAccountable(),
                 'orderable'                      : self.isOrderable(),
                 'deliverable'                    : self.isDeliverable(),
                 'variation_text'                 : self.getVariationText(),
                 'inventory'                      : self.getInventoriatedQuantity(),
                 'source_total_asset_price'       : 0.0,
                 'destination_total_asset_price'  : 0.0,
                } ]
    for m in self.objectValues():
      result.extend(m.getMovementIndex())
    return result

  security.declareProtected(Permissions.View, 'hasActivity')
  def hasActivity(self, **kw):
    """
      We reindex the whole applied rule
    """
    return self.getRootAppliedRule().hasActivity(**kw)

  security.declareProtected(Permissions.View, 'reindexObject')
  def reindexObject(self, **kw):
    """
      We reindex the whole applied rule (only once)
    """
    self.getRootAppliedRule().reindexObject() # Reindex the whole applied rule

  security.declareProtected(Permissions.AccessContentsInformation, 'getExplanation')
  def getExplanation(self):
    """
      Returns the delivery if any or the order related to the root applied rule if any
      Name should be changed to generic name (getExplanationUid)
    """
    if self.getDeliveryValue() is None:
      ra = self.getRootAppliedRule()
      order = ra.getCausalityValue()
      if order is not None:
        return order.getRelativeUrl()
      else:
        # Ex. zero stock rule
        return ra.getRelativeUrl()
    else:
      return self.getDelivery()

  security.declareProtected(Permissions.AccessContentsInformation, 'getExplanationUid')
  def getExplanationUid(self):
    """
      Returns the delivery if any or the order related to the root applied rule if any
      Name should be changed to generic name (getExplanationUid)
    """
    if self.getDeliveryValue() is None:
      ra = self.getRootAppliedRule()
      order = ra.getCausalityValue()
      if order is not None:
        return order.getUid()
      else:
        # Ex. zero stock rule
        return ra.getUid()
    else:
      return self.getDeliveryUid()

  security.declareProtected(Permissions.AccessContentsInformation, 'getExplanationValue')
  def getExplanationValue(self):
    """
      Returns the delivery if any or the order related to the root applied rule if any
      Name should be changed to generic name (getExplanationUid)
    """
    if self.getDeliveryValue() is None:
      ra = self.getRootAppliedRule()
      order = ra.getCausalityValue()
      if order is not None:
        return order
      else:
        # Ex. zero stock rule
        return ra
    else:
      return self.getDeliveryValue()

  def isFrozen(self):
    """
      A frozen simulation movement can not change its target anylonger

      Also, once a movement is frozen, we do not calculate anylonger
      its direct consequences. (ex. we do not calculate again a transformation)
    """
    return 0

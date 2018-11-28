#!/usr/bin/env python
# -*- coding: utf-8 -*-

#############################################################################
##
# This file is part of Taurus
##
# http://taurus-scada.org
##
# Copyright 2011 CELLS / ALBA Synchrotron, Bellaterra, Spain
##
# Taurus is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
##
# Taurus is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
##
# You should have received a copy of the GNU Lesser General Public License
# along with Taurus.  If not, see <http://www.gnu.org/licenses/>.
##
#############################################################################

"""This module provides a set of basic Taurus widgets based on QLed"""

__all__ = ["TaurusLed"]

__docformat__ = 'restructuredtext'

import weakref
import operator
import threading
from taurus.external.qt import Qt
import time
from taurus.core import DataFormat, AttrQuality, DataType

from taurus.qt.qtgui.base import TaurusBaseWidget
from qled import QLed
import taurus
import elasticapm
from taurus.core.util.event import (CallableRef,
                         BoundMethodWeakref)
from functools import wraps # This convenience func preserves name and docstring

_QT_PLUGIN_INFO = {
    'module': 'taurus.qt.qtgui.display',
    'group': 'Taurus Display',
    'icon': "designer:ledgreen.png",
}


class _TaurusLedController(object):

    #            key     status,     color, inTrouble
    LedMap = {True: (True,    "green",    False),
              False: (False,    "black",    False),
              None: (False,    "black",     True)}

    LedQualityMap = {
        AttrQuality.ATTR_ALARM: (True,   "orange",    False),
        AttrQuality.ATTR_CHANGING: (True,     "blue",    False),
        AttrQuality.ATTR_INVALID: (True,      "red",    False),
        AttrQuality.ATTR_VALID: (True,    "green",    False),
        AttrQuality.ATTR_WARNING: (True,   "orange",    False),
        None: (False,    "black",     True)}

    def __init__(self, widget):
        self._widget = weakref.ref(widget)

    def widget(self):
        return self._widget()

    def modelObj(self):
        return self.widget().getModelObj()

    def value(self):
        widget, obj = self.widget(), self.modelObj()
        fgRole = widget.fgRole
        value = None
        if fgRole == 'rvalue':
            value = obj.rvalue
        elif fgRole == 'wvalue':
            value = obj.wvalue
        elif fgRole == 'quality':
            return obj.quality

        # handle 1D and 2D values
        if obj.data_format is not DataFormat._0D:
            idx = widget.getModelIndexValue()
            if idx:
                for i in idx:
                    value = value[i]

        return bool(value)

    def usePreferedColor(self, widget):
        return True

    def handleEvent(self, evt_src, evt_type, evt_value):
        self.update()

    def update(self):
        widget = self.widget()

        self._updateDisplay(widget)
        self._updateToolTip(widget)

    def _updateDisplay(self, widget):
        key = None
        try:
            key = self.value()
        except Exception, e:
            pass
        ledMap = self.LedMap
        if widget.fgRole == 'quality':
            ledMap = self.LedQualityMap
        try:
            status, color, trouble = ledMap[key]
        except:
            status, color, trouble = False, "red", True
        if self.usePreferedColor(widget):
            if status:
                color = widget.onColor
            else:
                color = widget.offColor
        widget.ledStatus = status
        widget.ledColor = color
        if trouble:
            widget.setAutoFillBackground(True)
            bg_brush = Qt.QBrush(Qt.Qt.BDiagPattern)
            palette = widget.palette()
            palette.setBrush(Qt.QPalette.Window, bg_brush)
            palette.setBrush(Qt.QPalette.Base, bg_brush)
            widget.setPalette(palette)
        else:
            widget.setAutoFillBackground(False)

    def _updateToolTip(self, widget):
        widget.setToolTip(widget.getFormatedToolTip())


class _TaurusLedControllerBool(_TaurusLedController):

    def usePreferedColor(self, widget):
        # use prefered widget color if representing the boolean read or write
        # value. If representing the quality, use the quality map
        return widget.fgRole != 'quality'

try:
    from taurus.core.tango import DevState  # TODO: Tango-centric
    class _TaurusLedControllerState(_TaurusLedController):

        #                key      status,       color, inTrouble
        LedMap = {DevState.ON: (True,    "green",    False),
                  DevState.OFF: (False,    "black",    False),
                  DevState.CLOSE: (True,    "white",    False),
                  DevState.OPEN: (True,    "green",    False),
                  DevState.INSERT: (True,    "green",    False),
                  DevState.EXTRACT: (True,    "green",    False),
                  DevState.MOVING: (True,     "blue",    False),
                  DevState.STANDBY: (True,   "yellow",    False),
                  DevState.FAULT: (True,      "red",    False),
                  DevState.INIT: (True,   "yellow",    False),
                  DevState.RUNNING: (True,     "blue",    False),
                  DevState.ALARM: (True,   "orange",    False),
                  DevState.DISABLE: (True,  "magenta",    False),
                  DevState.UNKNOWN: (False,    "black",    False),
                  None: (False,    "black",     True)}

        def value(self):
            widget, obj = self.widget(), self.modelObj()
            fgRole = widget.fgRole
            value = None
            if fgRole == 'rvalue':
                value = obj.rvalue
            elif fgRole == 'wvalue':
                value = obj.wvalue
            elif fgRole == 'quality':
                value = obj.quality
            return value

        def usePreferedColor(self, widget):
            # never use prefered widget color. Use always the map
            return False
except:
    pass


class _TaurusLedControllerDesignMode(_TaurusLedController):

    def _updateDisplay(self, widget):
        widget.ledStatus = True
        if widget.ledStatus:
            widget.ledColor = widget.onColor
        else:
            widget.ledColor = widget.offColor
        widget.setAutoFillBackground(False)

    def _updateToolTip(self, widget):
        widget.setToolTip("Design mode TaurusLed")


class TaurusLed(QLed, TaurusBaseWidget):
    """A widget designed to represent with a LED image the state of a device,
    the value of a boolean attribute or the quality of an attribute."""

    DefaultModelIndex = None
    DefaultFgRole = 'rvalue'
    DefaultOnColor = "green"
    DefaultOffColor = "black"

    _deprecatedRoles = dict(value='rvalue', w_value='wvalue')

    def __init__(self, parent=None, designMode=False):
        name = self.__class__.__name__
        self._designMode = designMode
        self._modelIndex = self.DefaultModelIndex
        self._modelIndexStr = ''
        self._fgRole = self.DefaultFgRole
        self._onColor = self.DefaultOnColor
        self._offColor = self.DefaultOffColor
        self._controller = None
        self.call__init__wo_kw(QLed, parent)
        self.call__init__(TaurusBaseWidget, name, designMode=designMode)

        # if we are in design mode there will be no events so we force the
        # creation of a controller object
        if self._designMode:
            self.controller().update()
        if parent is not None:
            service_name = parent
        else:
            service_name = self.log_name

        self.client = elasticapm.Client({'SERVICE_NAME': service_name})
        self.events_received = 0
        self.events_ts = []
        self._events_fr = {}
        self._events_fr[1] = []
        self._events_fr[10] = []
        self.t = threading.Thread(target=self.calculate_events)
        self.t.start()

    def calculate_events(self):
        t1 = time.time()
        t = 1
        while True:
            time.sleep(t)
            ev = len(self.events_ts)
            self.events_ts = []
            for i in self._events_fr.keys():
                self._events_fr[i].append(ev)
                if len(self._events_fr[i]) > (i/t):
                    self._events_fr[i].pop()
            if time.time() - t1 > 10:
                self.controller().update()
                t1 = time.time()

    def addListeners(self):
        factory = taurus.Factory()
        attrs = factory.getExistingAttributes()
        for attr_name, attr_obj in attrs.items():

            # To add APM min the listeners
            listeners = attr_obj._listeners
            if listeners is None:
                continue

            if not operator.isSequenceType(listeners):
                listeners = listeners,

            for listener in listeners:
                if isinstance(listener, weakref.ref) or isinstance(listener,
                                                                   BoundMethodWeakref):
                    l = listener()
                else:
                    l = listener
                if l is None:
                    continue
                meth = getattr(l, 'eventReceived', None)
                if meth is not None and operator.isCallable(meth):
                    org = l.eventReceived
                    l.eventReceived = self.transaction_dec(self.span_dec(org))
                elif operator.isCallable(l):
                    org = l
                    l = self.transaction_dec(self.span_dec(org))

            # To Count the time between the event creation and the event
            # managment
            attr_obj.addListener(self.diagnostic_listener)
            print 'listener added'

    def span_dec(self, f):

        @elasticapm.capture_span()
        @wraps(f)
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs)
        return wrapper


    # Decorator to use APM
    def transaction_dec(self, f):

        def wrapper(*args, **kwargs):
            #client = elasticapm.Client({'SERVICE_NAME': 'Taurus Listeners'})

            self.client.begin_transaction(f.func_name)

            ret = f(*args, **kwargs)
            self.client.end_transaction(self.modelName, 'SUCCCESS')
            return ret
        return wrapper

    def diagnostic_listener(self, src, type, value):
        try:
            source_time = value.time.tv_sec
        except:
            return
        transaction = self.client.begin_transaction('Event Source Listener '
                                                    'Time')
        context = {
            'args': str(src) +'\n.'+str(value),
            'kwards': repr(self),
        }
        elasticapm.set_custom_context(context)
        transaction.start_time = time.time() - (time.time() - source_time)
        self.client.end_transaction(src.fullname, 'SUCCESS')# value.value)
        self.events_received += 1
        self.events_ts.append(time.time())


    def getFormatedToolTip(self, cache=True):
        """ The tooltip should refer to the device and not the state attribute.
            That is why this method is being rewritten
        """
        if self.modelObj is None:
            return self.getNoneValue()
        parent = self.modelObj.getParentObj()
        if parent is None:
            return self.getNoneValue()
        return self.toolTipObjToStr(self.getDisplayDescrObj() )

    def getDisplayDescrObj(self, cache=True):
        obj = []
        obj.append(('Events_received', self.events_received))
        for i in self._events_fr.keys():
            l = self._events_fr[i]
            if len(l) == 0:
                val = 0
            else:
                val = sum(l) / float(len(l))
            obj.append(('Average Hz in %s secs' %i, val))
        return obj

    def _calculate_controller_class(self):
        model = self.getModelObj()

        klass = _TaurusLedController
        if self._designMode:
            klass = _TaurusLedControllerDesignMode
        elif model is None:
            klass = _TaurusLedController
        elif model.isBoolean():
            klass = _TaurusLedControllerBool
        elif model.type == DataType.DevState:
            klass = _TaurusLedControllerState  # TODO: tango-centric
        return klass

    def controller(self):
        ctrl = self._controller
        # if there is a controller object and it is not the base controller...
        if ctrl is not None and not ctrl.__class__ == _TaurusLedController:
            return ctrl

        # if there is a controller object and it is still the same class...
        ctrl_klass = self._calculate_controller_class()
        if ctrl is not None and ctrl.__class__ == ctrl_klass:
            return ctrl

        self._controller = ctrl = ctrl_klass(self)
        return ctrl

    #-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
    # TaurusBaseWidget overwriting
    #-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

    def handleEvent(self, evt_src, evt_type, evt_value):
        self.controller().handleEvent(evt_src, evt_type, evt_value)

    def isReadOnly(self):
        return True

    def setModel(self, m):
        # force to build another controller
        self._controller = None
        TaurusBaseWidget.setModel(self, m)
        self.addListeners()

    #-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
    # QT property definition
    #-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

    def getFgRole(self):
        return self._fgRole

    def setFgRole(self, fgRole):
        role = self._deprecatedRoles.get(fgRole, fgRole)
        if fgRole != role:
            self.deprecated(rel='4.0', dep='setFgRole(%s)' % fgRole,
                            alt='setFgRole(%s)' % role)
        self._fgRole = str(role)
        self.controller().update()

    def resetFgRole(self):
        self.setFgRole(self.DefaultFgRole)

    def getOnColor(self):
        """Returns the preferred led on color
        :return: led on color
        :rtype: str"""
        return self._onColor

    def setOnColor(self, color):
        """Sets the preferred led on color
        :param status: the new on color
        :type  status: str"""
        color = str(color).lower()
        if not self.isLedColorValid(color):
            raise Exception("Invalid color '%s'" % color)
        self._onColor = color
        self.controller().update()

    def resetOnColor(self):
        """Resets the preferred led on color"""
        self.setOnColor(self.DefaultOnColor)

    def getOffColor(self):
        """Returns the preferred led off color
        :return: led off color
        :rtype: str"""
        return self._offColor

    def setOffColor(self, color):
        """Sets the preferred led off color
        :param status: the new off color
        :type  status: str"""
        color = str(color).lower()
        if not self.isLedColorValid(color):
            raise Exception("Invalid color '%s'" % color)
        self._offColor = color
        self.controller().update()

    def resetOffColor(self):
        """Resets the preferred led color"""
        self.setOffColor(self.DefaultOffColor)

    def getModelIndexValue(self):
        return self._modelIndex

    def getModelIndex(self):
        return self._modelIndexStr

    def setModelIndex(self, modelIndex):
        mi = str(modelIndex)
        if len(mi) == 0:
            self._modelIndex = None
        else:
            try:
                mi_value = eval(str(mi))
            except:
                return
            if type(mi_value) == int:
                mi_value = mi_value,
            if not operator.isSequenceType(mi_value):
                return
            self._modelIndex = mi_value
        self._modelIndexStr = mi
        self.controller().update()

    def resetModelIndex(self):
        self.setModelIndex(self.DefaultModelIndex)

    @classmethod
    def getQtDesignerPluginInfo(cls):
        d = TaurusBaseWidget.getQtDesignerPluginInfo()
        d.update(_QT_PLUGIN_INFO)
        return d

    #: This property holds the unique URI string representing the model name
    #: with which this widget will get its data from. The convention used for
    #: the string can be found :ref:`here <model-concept>`.
    #:
    #: **Access functions:**
    #:
    #:     * :meth:`TaurusBaseWidget.getModel`
    #:     * :meth:`TaurusLabel.setModel`
    #:     * :meth:`TaurusBaseWidget.resetModel`
    #:
    #: .. seealso:: :ref:`model-concept`
    model = Qt.pyqtProperty("QString", TaurusBaseWidget.getModel, setModel,
                            TaurusBaseWidget.resetModel)

    #: This property holds whether or not this widget should search in the
    #: widget hierarchy for a model prefix in a parent widget.
    #:
    #: **Access functions:**
    #:
    #:     * :meth:`TaurusBaseWidget.getUseParentModel`
    #:     * :meth:`TaurusBaseWidget.setUseParentModel`
    #:     * :meth:`TaurusBaseWidget.resetUseParentModel`
    #:
    #: .. seealso:: :ref:`model-concept`
    useParentModel = Qt.pyqtProperty("bool", TaurusBaseWidget.getUseParentModel,
                                     TaurusBaseWidget.setUseParentModel,
                                     TaurusBaseWidget.resetUseParentModel)

    #: This property holds the index inside the model value that should be
    #: displayed
    #:
    #: **Access functions:**
    #:
    #:     * :meth:`TaurusLed.getModelIndex`
    #:     * :meth:`TaurusLed.setModelIndex`
    #:     * :meth:`TaurusLed.resetModelIndex`
    #:
    #: .. seealso:: :ref:`model-concept`
    modelIndex = Qt.pyqtProperty("QString", getModelIndex, setModelIndex,
                                 resetModelIndex)

    #: This property holds the foreground role.
    #: Valid values are:
    #:
    #:     #. 'value' - the value is used
    #:     #. 'w_value' - the write value is used
    #:     #. 'quality' - the quality is used
    #:
    #: **Access functions:**
    #:
    #:     * :meth:`TaurusLed.getFgRole`
    #:     * :meth:`TaurusLed.setFgRole`
    #:     * :meth:`TaurusLed.resetFgRole`
    fgRole = Qt.pyqtProperty("QString", getFgRole, setFgRole,
                             resetFgRole, doc="foreground role")

    #: This property holds the preferred led color
    #: This value is used for the cases where the model value does not contain
    #: enough information to distinguish between different On colors.
    #: For example, a bool attribute, when it is False it is displayed with the
    #: off led but when it is true it may be displayed On in any color. The
    #: prefered color would be used in this case.
    #:
    #: **Access functions:**
    #:
    #:     * :meth:`TaurusLed.getOnColor`
    #:     * :meth:`TaurusLed.setOnColor`
    #:     * :meth:`TaurusLed.resetOnColor`
    onColor = Qt.pyqtProperty("QString", getOnColor, setOnColor, resetOnColor,
                              doc="preferred led On color")

    #: This property holds the preferred led color
    #: This value is used for the cases where the model value does not contain
    #: enough information to distinguish between different Off colors.
    #: For example, a bool attribute, when it is False it is displayed with the
    #: off led but when it is true it may be displayed On in any color. The
    #: prefered color would be used in this case.
    #:
    #: **Access functions:**
    #:
    #:     * :meth:`TaurusLed.getOffColor`
    #:     * :meth:`TaurusLed.setOffColor`
    #:     * :meth:`TaurusLed.resetOffColor`
    offColor = Qt.pyqtProperty("QString", getOffColor, setOffColor, resetOffColor,
                               doc="preferred led Off color")


def demo():
    "Led"
    import demo.taurusleddemo
    return demo.taurusleddemo.main()


def main():
    import sys
    import taurus.qt.qtgui.application
    Application = taurus.qt.qtgui.application.TaurusApplication

    app = Application.instance()
    owns_app = app is None

    if owns_app:
        import taurus.core.util.argparse
        parser = taurus.core.util.argparse.get_taurus_parser()
        parser.usage = "%prog [options] <full_attribute_name(s)>"
        app = Application(sys.argv, cmd_line_parser=parser,
                          app_name="Taurus led demo", app_version="1.0",
                          org_domain="Taurus", org_name="Tango community")

    args = app.get_command_line_args()

    if len(args) == 0:
        w = demo()
    else:
        models = map(str.lower, args)

        w = Qt.QWidget()
        layout = Qt.QGridLayout()
        w.setLayout(layout)
        for model in models:
            led = TaurusLed(parent=app)
            led.model = model
            layout.addWidget(led)
    w.show()

    if owns_app:
        sys.exit(app.exec_())
    else:
        return w

if __name__ == '__main__':
    main()

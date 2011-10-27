#!/usr/bin/env python

#############################################################################
##
## This file is part of Taurus, a Tango User Interface Library
## 
## http://www.tango-controls.org/static/taurus/latest/doc/html/index.html
##
## Copyright 2011 CELLS / ALBA Synchrotron, Bellaterra, Spain
## 
## Taurus is free software: you can redistribute it and/or modify
## it under the terms of the GNU Lesser General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
## 
## Taurus is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU Lesser General Public License for more details.
## 
## You should have received a copy of the GNU Lesser General Public License
## along with Taurus.  If not, see <http://www.gnu.org/licenses/>.
##
#############################################################################
"""
This module contains a list of codecs for the DEV_ENCODED attribute type.
All codecs are based on the pair *format, data*. The format is a string 
containing the codec signature and data is a sequence of bytes (string) 
containing the encoded data. 

This module contains a list of codecs capable of decoding several codings like
bz2, zip and json.

The :class:`CodecFactory` class allows you to get a codec object for a given 
format and also to register new codecs.
The :class:`CodecPipeline` is a special codec that is able to code/decode a
sequence of codecs. This way you can have codecs 'inside' codecs.

Example::

    >>> from taurus.core.util import CodecFactory
    >>> cf = CodecFactory()
    >>> json_codec = cf.getCodec('json')
    >>> bz2_json_codec = cf.getCodec('bz2_json')
    >>> data = range(100000)
    >>> f1, enc_d1 = json_codec.encode(('', data))
    >>> f2, enc_d2 = bz2_json_codec.encode(('', data))
    >>> print len(enc_d1), len(enc_d2)
    688890 123511
    >>> 
    >>> f1, dec_d1 = json_codec.decode((f1, enc_d1))
    >>> f2, dec_d2 = bz2_json_codec.decode((f2, enc_d2))

A Taurus related example::

    >>> # this example shows how to automatically get the data from a DEV_ENCODED attribute
    >>> import taurus
    >>> from taurus.core.util import CodecFactory
    >>> cf = CodecFactory()
    >>> devenc_attr = taurus.Attribute('a/b/c/devenc_attr')
    >>> v = devenc_attr.read()
    >>> codec = CodecFactory().getCodec(v.format)
    >>> f, d = codec.decode((v.format, v.value))
"""

__all__ = ["Codec", "NullCodec", "ZIPCodec", "BZ2Codec", "JSONCodec",
           "FunctionCodec", "PlotCodec", "CodecPipeline", "CodecFactory"]

__docformat__ = "restructuredtext"

import copy
import operator
import types

from singleton import Singleton
from log import Logger, DebugIt
from containers import CaselessDict

from taurus.core.util import json


class Codec(Logger):
    """The base class for all codecs"""
    
    def __init__(self):
        """Constructor"""
        Logger.__init__(self, self.__class__.__name__)
    
    def encode(self, data, *args, **kwargs):
        """encodes the given data. This method is abstract an therefore must
        be implemented in the subclass.
            
        :param data: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object
        
        :return: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object
        
        :raises: RuntimeError"""
        raise RuntimeError("decode cannot be called on abstract Codec")
    
    def decode(self, data, *args, **kwargs):
        """decodes the given data. This method is abstract an therefore must
        be implemented in the subclass.
        
        :param data: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object
        
        :return: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object
        
        :raises: RuntimeError"""
        raise RuntimeError("decode cannot be called on abstract Codec")

    def __str__(self):
        return '%s()' % self.__class__.__name__
    
    def __repr__(self):
        return '%s()' % self.__class__.__name__


class NullCodec(Codec):

    def encode(self, data, *args, **kwargs):
        """encodes with Null encoder. Just returns the given data

        :param data: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object
        
        :return: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object"""
        return data
    
    def decode(self, data, *args, **kwargs):
        """decodes with Null encoder. Just returns the given data

        :param data: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object
        
        :return: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object"""
        return data


class ZIPCodec(Codec):
    """A codec able to encode/decode to/from gzip format. It uses the :mod:`zlib` module
    
    Example::
    
        >>> from taurus.core.util import CodecFactory
        
        >>> # first encode something
        >>> data = 100 * "Hello world\\n"
        >>> cf = CodecFactory()
        >>> codec = cf.getCodec('zip')
        >>> format, encoded_data = codec.encode(("", data))
        >>> print len(data), len(encoded_data)
        1200, 31
        >>> format, decoded_data = codec.decode((format, encoded_data))
        >>> print decoded_data[20]
        'Hello world\\nHello wo'"""
    
    def encode(self, data, *args, **kwargs):
        """encodes the given data to a gzip string. The given data **must** be a string
        
        :param data: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object
        
        :return: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object"""
        import zlib
        format = 'zip'
        if len(data[0]): format += '_%s' % data[0]
        return format, zlib.compress(data[1])
    
    def decode(self, data, *args, **kwargs):
        """decodes the given data from a gzip string.
            
        :param data: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object
        
        :return: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object"""
        import zlib
        if not data[0].startswith('zip'):
            return data
        format = data[0].partition('_')[2]
        return format, zlib.decompress(data[1])


class BZ2Codec(Codec):
    """A codec able to encode/decode to/from BZ2 format. It uses the :mod:`bz2` module

    Example::
    
        >>> from taurus.core.util import CodecFactory
        
        >>> # first encode something
        >>> data = 100 * "Hello world\\n"
        >>> cf = CodecFactory()
        >>> codec = cf.getCodec('bz2')
        >>> format, encoded_data = codec.encode(("", data))
        >>> print len(data), len(encoded_data)
        1200, 68
        >>> format, decoded_data = codec.decode((format, encoded_data))
        >>> print decoded_data[20]
        'Hello world\\nHello wo'"""
    
    def encode(self, data, *args, **kwargs):
        """encodes the given data to a bz2 string. The given data **must** be a string
        
        :param data: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object
        
        :return: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object"""
        import bz2
        format = 'bz2'
        if len(data[0]): format += '_%s' % data[0]
        return format, bz2.compress(data[1])
    
    def decode(self, data, *args, **kwargs):
        """decodes the given data from a bz2 string.
            
        :param data: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object
        
        :return: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object"""
        import bz2
        if not data[0].startswith('bz2'):
            return data
        format = data[0].partition('_')[2]
        return format, bz2.decompress(data[1])


class JSONCodec(Codec):
    """A codec able to encode/decode to/from json format. It uses the :mod:`json` module.
    
    Example::
        
        >>> from taurus.core.util import CodecFactory
        
        >>> cf = CodecFactory()
        >>> codec = cf.getCodec('json')
        >>>
        >>> # first encode something
        >>> data = { 'hello' : 'world', 'goodbye' : 1000 }
        >>> format, encoded_data = codec.encode(("", data))
        >>> print encoded_data
        '{"hello": "world", "goodbye": 1000}'
        >>>
        >>> # now decode it
        >>> format, decoded_data = codec.decode((format, encoded_data))
        >>> print decoded_data
        {'hello': 'world', 'goodbye': 1000}"""
    
    def encode(self, data, *args, **kwargs):
        """encodes the given data to a json string. The given data **must** be a python
        object that json is able to convert.
            
        :param data: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object
        
        :return: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object"""
        format = 'json'
        if len(data[0]): format += '_%s' % data[0]
        # make it compact by default
        kwargs['separators'] = kwargs.get('separators', (',',':'))
        return format, json.dumps(data[1], *args, **kwargs)
    
    def decode(self, data, *args, **kwargs):
        """decodes the given data from a json string.
            
        :param data: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object
        
        :return: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object"""
        if not data[0].startswith('json'):
            return data
        format = data[0].partition('_')[2]
        
        ensure_ascii = False
        if 'ensure_ascii' in kwargs:
            ensure_ascii = kwargs.pop('ensure_ascii')
        
        if isinstance(data[1], buffer):
            data = data[0], str(data[1])
        
        data = json.loads(data[1])
        if ensure_ascii:
            data = self._transform_ascii(data)
        return format, data

    def _transform_ascii(self, data):
        if isinstance(data, unicode):
            return data.encode('utf-8')
        elif isinstance(data, dict):
            return self._transform_dict(data)
        elif isinstance(data, list):
            return self._transform_list(data)
        elif isinstance(data, tuple):
            return tuple(self._transform_list(data))
        else:
            return data
        
    def _transform_list(self, lst):
        return [ self._transform_ascii(item) for item in lst ]

    def _transform_dict(self, dct):
        newdict = {}
        for k, v in dct.iteritems():
            newdict[self._transform_ascii(k)] = self._transform_ascii(v)
        return newdict


class FunctionCodec(Codec):
    """A generic function codec"""
    def __init__(self, func_name):
        Codec.__init__(self)
        self._func_name = func_name
    
    def encode(self, data, *args, **kwargs):
        return self._func_name, { 'type' : self._func_name, 'data' : data }
    
    def decode(self, data, *args, **kwargs):
        if not data[0].startswith(self._func_name):
            return data
        format = data[0].partition('_')[2]
        return format, data[1]


class PlotCodec(FunctionCodec):
    """A specialization of the :class:`FunctionCodec` for plot function"""    
    def __init__(self):
        FunctionCodec.__init__(self, 'plot')


class CodecPipeline(Codec, list):
    """The codec class used when encoding/decoding data with multiple encoders

    Example usage::
        
        >>> from taurus.core.util import CodecPipeline
        
        >>> data = range(100000)
        >>> codec = CodecPipeline('bz2_json')
        >>> format, encoded_data = codec.encode(("", data))
        
        # decode it 
        format, decoded_data = codec.decode((format, encoded_data))
        print decoded_data"""
        
    def __init__(self, format):
        """Constructor. The CodecPipeline object will be created using 
        the :class:`CodecFactory` to search for format(s) given in the format
        parameter.
        
        :param format: (str) a string representing the format."""
        
        Codec.__init__(self)
        list.__init__(self)
        
        f = CodecFactory()
        for i in format.split('_'):
            codec = f.getCodec(i)
            self.debug("Appending %s => %s" % (i,codec))
            if codec is None:
                raise TypeError('Unsupported codec %s (namely %s)' % (format, i))
            self.append(codec)
        self.debug("Done")
        
    def encode(self, data, *args, **kwargs):
        """encodes the given data.
        
        :param data: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object
        
        :return: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object"""
        for codec in reversed(self):
            data = codec.encode(data, *args, **kwargs)
        return data
    
    def decode(self, data, *args, **kwargs):
        """decodes the given data.

        :param data: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object
        
        :return: (sequence[str, obj]) a sequence of two elements where the first item is the encoding format of the second item object"""
        for codec in self:
            data = codec.decode(data, *args, **kwargs)
        return data


class CodecFactory(Singleton, Logger):
    """The singleton CodecFactory class.
    
    To get the singleton object do::
    
        from taurus.core.util import CodecFactory
        f = CodecFactory()
        
    The :class:`CodecFactory` class allows you to get a codec object for a given 
    format and also to register new codecs.
    The :class:`CodecPipeline` is a special codec that is able to code/decode a
    sequence of codecs. This way you can have codecs 'inside' codecs.

    Example::

        >>> from taurus.core.util import CodecFactory
        >>> cf = CodecFactory()
        >>> json_codec = cf.getCodec('json')
        >>> bz2_json_codec = cf.getCodec('bz2_json')
        >>> data = range(100000)
        >>> f1, enc_d1 = json_codec.encode(('', data))
        >>> f2, enc_d2 = bz2_json_codec.encode(('', data))
        >>> print len(enc_d1), len(enc_d2)
        688890 123511
        >>> 
        >>> f1, dec_d1 = json_codec.decode((f1, enc_d1))
        >>> f2, dec_d2 = bz2_json_codec.decode((f2, enc_d2))

    A Taurus related example::

        >>> # this example shows how to automatically get the data from a DEV_ENCODED attribute
        >>> import taurus
        >>> from taurus.core.util import CodecFactory
        >>> cf = CodecFactory()
        >>> devenc_attr = taurus.Attribute('a/b/c/devenc_attr')
        >>> v = devenc_attr.read()
        >>> codec = CodecFactory().getCodec(v.format)
        >>> f, d = codec.decode((v.format, v.value))
    """
    
    #: Default minimum map of registered codecs
    CODEC_MAP = CaselessDict({
        'json' : JSONCodec,
        'bz2'  : BZ2Codec,
        'zip'  : ZIPCodec,
        'plot' : PlotCodec,
        'null' : NullCodec,
        'none' : NullCodec,
        ''     : NullCodec })

    def __init__(self):
        """ Initialization. Nothing to be done here for now."""
        pass

    def init(self, *args, **kwargs):
        """Singleton instance initialization."""
        name = self.__class__.__name__
        self.call__init__(Logger, name)
        
        self._codec_klasses = copy.copy(CodecFactory.CODEC_MAP)
        
        # dict<str, Codec> 
        # where:
        #  - key is the codec format
        #  - value is the codec object that supports the format
        self._codecs = CaselessDict()

    def registerCodec(self, format, klass):
        """Registers a new codec. If a codec already exists for the given format
        it is removed.
        
        :param format: (str) the codec id
        :param klass: (Codec class) the class that handles the format"""
        self._codec_klasses[format] = klass
        
        # del old codec if exists
        if self._codecs.has_key(format):
            del self._codecs[format]

    def unregisterCodec(self, format):
        """Unregisters the given format. If the format does not exist an exception
        is thrown.
        
        :param format: (str) the codec id
        
        :raises: KeyError"""
        if self._codec_klasses.has_key(format):
            del self._codec_klasses[format]
        
        if self._codecs.has_key(format):
            del self._codecs[format]

    def getCodec(self, format):
        """Returns the codec object for the given format or None if no suitable
        codec is found
        
        :param format: (str) the codec id
        
        :return: (Codec or None) the codec object for the given format"""
        codec = self._codecs.get(format)
        if codec is None:
            codec = self._getNewCodec(format)
            if not codec is None: self._codecs[format] = codec
        return codec
        
    def _getNewCodec(self, format):
        klass = self._codec_klasses.get(format)
        if not klass is None:
            ret = klass()
        else:
            try:
                ret = CodecPipeline(format)
            except:
                ret = self._codec_klasses.get('')()
        return ret
    
    def decode(self, data, *args, **kwargs):
        return self.getCodec(data[0]).decode(data, *args, **kwargs)[1]
        
    def encode(self, data, *args, **kwargs):
        return self.getCodec(data[0]).encode(data, *args, **kwargs)[1]
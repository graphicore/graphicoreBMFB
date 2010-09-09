#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Build fonts from a custom format "Bitmap Font" (BMF) into OpenType, TrueType or something else."""
#    This file is part of graphicore Bitmap Font Building.
#
#    graphicore Bitmap Font Building, this program builds bitmap fonts
#    Copyright (c) 2010, Lasse Fister lasse@graphicore.de, http://graphicore.de
#
#    graphicore Bitmap Font Building is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import with_statement

import sys
import os
import re
import codecs
import math
import json
import random

import fontforge

#these values are not changeable by the option files
#but possibly via commandline options and of course programmatically
settings = {
    'outputFolder' : './generated',
    #this will protect against infinite recursive loading of optionfiles
    'maxInstructionsLoadingDepth' : 50,
    'verbosityLevel': -1,
    #get more at http://www.microsoft.com/typography/otspec/name.htm and extend these if needed
    # I did not get it to work with the string names fontforge uses, but fontforge took these numeric values
    'sfntLookup':
    {
        'English' : 0,
        'French' : 1,
        'German' : 2,
        'Italian' : 3,
        'Dutch' : 4,

        'Copyright' : 0,
        'Family' : 1,
        'SubFamily': 2,
        'Trademark' : 7,
        'Manufacturer' : 8,
        'Designer' : 9,
        'Descriptor': 10,
        'Vendor URL' : 11,
        'Designer URL': 12,
        'License' : 13,
        'License URL' : 14,
    }
}
def version():
    return '0.1'
def vprint(*args, **kwargs):
    """Print *args to stdout if level is smaller or equal to settings['verbosityLevel']."""
    level = int(kwargs.get('level', 0))
    if settings['verbosityLevel'] < 0 or level > settings['verbosityLevel']:
        return;
    for index,arg in enumerate(args):
        try:
            sys.stdout.write(str(arg))
        except UnicodeEncodeError, e:
            sys.stdout.write(arg.encode('utf-8'))
        if(index < len(args) -1 ):
            sys.stdout.write(' ')
    sys.stdout.write('\n')

defaults = {
# these options are written with double quotes because that yields in valid json, making copy and paste faster
# expept booleans, which are first letter lowercase in json: false and true instead of False and True in Python
# except escaped unicode wich is in python like 'a' : u"\ue8ff"' and in json like 'a' : "\ue8ff"
# except comments, which where a cool feature for json configuration files
    "font" : {
        "fileName" : "unnamed",
        #a .fea file to be merged directly
        "featureFile" : False,
        "glyphFolder" : "glyphs",
        #the height of all glyphs, the glyphs will be cropped or padded if necessary
        "lineCount" : 12,
        #from the bottom, count of lines below the baseline
        "descent" : 2,
        #underline position from the baseline
        "upos" : 3,
        #underline height
        "uwidth" : 1,
        #in a glyph this is a filled pixel
        "filled" : "#",
        #in a glyph this is an empty
        "empty" : ".",
        "classRightIndicator": u"@_1R",
        "classLeftIndicator": u"@_2L"
    },
    #a dict that maps names to utf codepoints, and will always be used first if set in UnicodeAndNames
    "name2Unicode" : {},#in python like 'a' : u"\ue8ff"' in json like 'a' : "\ue8ff"
    "metadata": {
        #postscript names, as used in fontforge
        "fontname" : "unnamed-medium",
        "weight" : "Medium",
        "fullname" : "unnamed medium",
        "familyname" : "unnamed",
        "copyright" : "Copyright (c), put your notice here.",
        "version" : "0",
        "more": {
            "English": {
                "Manufacturer": "unnamed",
                "Designer" : "unnamed",
                "Designer URL" : "http://unnamed",
                "Vendor URL" : "http://unnamed",
                "License": "no text",
                "License URL":  "http://unnamed",
                "Trademark": "",
                "Descriptor" : "Built with graphicore Boolean Matrix Font Building and fontforge. http://graphicore.de",
            }
        }
    },
    "generator": {
        #one raster unit in em
        "unit" : 125,
        #the x and y offset of the final pixel shape
        "offset" : 5,
        #the width (diameter) of the final pixel shape
        "width" : 115,
        #the fonts em height usually 1000 for postscript font and for truetyoe a power of 2, such as 2048
        "em" : 1000,
        #if set here the descent is not beeing calculated, thus givin some control over it
        "emDescent" :200,
        #magical thing
        "contextualShape" : False,
        #a value biger than 0 will turn on contextualShapes for outside corners. i.e. corners where otherwise nothing would have been drawn
        #the combination: offset > 0 and width < unit and itself outsideCornerRadius = 0.5 fontforge has problems removing the overlaps in some chars
        #making outsideCornerRadius (width/2) -1 is the best solution I know so far
        "outsideCornerRadius" : 0,
        "insideCornerRadius" : 0,
        #a .fea file that will be generated (and then merged).
        "generatedFeatureFile" : False,
        "generatedClassesFile" : "classes.jsn",
        "generatedKerningFile" : "kerning.jsn",
        "fileFormats": ['otf', 'sfd'],
        "ffGenerateFlags" : ["opentype", "old-kern", "dummy-dsig"],
        "removeOverlap" : True,
        #an either good idea, but slow
        "autoHint" : True,
        "invertOutside" : False
    },
    #dict of glyphsNames : glyphFiles.txt
    "glyphs": {},
    "features" : {
        #dict of "kerningclassname" : ["list of space separated glyphnames a b c comma"]
        "kerningClasses": {},
        #dict of "keringclassname" : int(always ad on this side) #this is not the dist table
        #distances stores the left and right sidebearing of the characters in the kerning class
        "distances" : {},
        #list of ["rightEdgeKerningClass", "leftEdgeKerningKlass", int(distance)[, bool enum]]
        "kern" : [],
        #list of ligatures ["replace space separated like f f i", "by_a_single_glyph_like_f_f_i"]
        "liga" : [],
        "dlig" : [],
        #all features here are made for all the following languagesystems : pairs of cryptic 4 letter words ["script", "language"]
        #for real good international magic some work would be required
        "languagesystems" : [["DFLT", "dflt"],["latn", "dflt"]]
    }
}

#see: http://www.whizkidtech.redprince.net/bezier/circle/
#kappa * radius(r) is the distance (d) between the oncurve point and the next ofcurve point needed to draw a sufficient circle
#a quater circle would be like moveTo((x,y)), curveTo((x, y + d), (x + r - d, y + r), (x + r, y + r)), closPath()
kappa = 4*((math.sqrt(2)-1)/3)
class FontError(Exception): pass
class GeneratorError(Exception): pass
class OptionsError(Exception): pass

class UnicodeAndNames(object):
    """
    Does some of the name finding for the author of a font.

    Usually lives in an object of Font.
    Will return the same results during its lifetime.
    """
    _cache = None
    #a dict set manually, if there is a key of a glyph name the ord() value of that value will be retutned as unicodepoint
    #this is to give the author of a font the possibillity tho set the unicodepoints for his chars reliable and repeatable to the same value
    name2Unicode = {}
    #Private Use Area (PUA) U+E000 to U+F8FF (57344–63743)
    #start somewhere, ... there is some space for other usage before
    _nextPUAPoint = 0xE8FF#59647
    nameGetter = None

    def __init__(self, name2Unicode = {}):
        self._cache = {'name' : {}, 'PUA' : {}}
        self.name2Unicode.update(name2Unicode)
        #this will be used with map
        def nameGetter(name):
            return self.getUnicodeAndName(name)[1]
        self.nameGetter = nameGetter

    def getPUACodePoint(self, name):
        """Return a codepoint from the private use area for name, if name was requested before, return the old value."""
        if name not in  self._cache['PUA']:
            self._cache['PUA'][name] = self._nextPUAPoint
            self._nextPUAPoint += 1
        return  self._cache['PUA'][name]

    def _byUserDict(self, name):
        """Return a tuple of unicode codepoint and name if name is a key in self name2Unicode or False."""
        try:
            return (ord(self.name2Unicode[name]), str(name))
        except KeyError:
            return False

    def _byValue(self, name):
        """Return a tuple of unicode codepoint and name if name is the string representation of the unicodepoint otherwise Retun False. Name is translated by fontforge.nameFromUnicode()."""
        try:
            uni = ord(name)
            return (uni, str(fontforge.nameFromUnicode(uni)))
        except TypeError, e:
            return False

    def _byName(self, name):
        """Return a tuple of unicode codepoint and name or False if name was not found by fontforge.unicodeFromName."""
        uni = fontforge.unicodeFromName(name)
        if uni > -1:
            return (uni, str(name))
        return False

    def _byPUA(self, name):
        """Return tuple of a private use area unicodepoint and the given name."""
        uni = self.getPUACodePoint(name)
        return (uni, str(name))

    def getUnicodeAndName(self, name):
        """
        Return a tuple of unicode and name for name.

        The method asks in order _byUserDict, _byValue, _byName, _byPUA for a unicodepoint and a name.
        The first name that produced a unicodepoint will always be returned for that unicodepoint in the lifetime of this object
        .
        """
        for func in (self._byUserDict, self._byValue, self._byName, self._byPUA):
            val = func(name)
            if val: break
        uni, returnedName = val
        if uni not in self._cache['name']:
            self._cache['name'][uni] = returnedName
        return (uni, self._cache['name'][uni])

    def getName(self, name):
        """Return the name that is returned for name by getUnicodeAndName()"""
        return self.getUnicodeAndName(name)[1]

    def getUnicode(self, name):
        """Return the unicodepoint that is returned for name by getUnicodeAndName()"""
        return self.getUnicodeAndName(name)[0]


def loadJson(fileName,  encoding='utf-8'):
    """Load json from fileName. By default with utf-8 encoding. Return a dict or a list."""
    with codecs.open(fileName, mode='r', encoding=encoding) as file:
        try:
            data = json.load(file)
            vprint('loaded json from %s' % fileName, level = 2)
        except ValueError:
            vprint(fileName, 'caused an error while loading it as json, probably a syntax error in the json.', level = 0)
            raise
    return data

def writeJson(fileName, data, encoding='utf-8'):
    """Write json to fileName. By default with utf-8 encoding."""
    with codecs.open(fileName, mode='wb', encoding=encoding) as file:
        json.dump(data, file, ensure_ascii=False, encoding=encoding, sort_keys=True, indent=1)#
        vprint('wrote json to %s' % fileName, level = 1)
    return True#no exception...

def loadInstructions(filename):
    """Load instructions from json files recursiveley, only setting values that have not been set before. Return the final object."""
    stack = [(filename, 0)]
    loaded = []
    options = {}
    maxDepth = settings['maxInstructionsLoadingDepth']
    while len(stack):
        filedata = stack.pop()
        loaded.append(filedata)
        filename, depth = filedata
        vprint ('loading options: %s, depth of %d' % filedata, level = 2)
        if depth >= maxDepth:
            raise OptionsError('loading a file deeper than %d is not permitted to prevent recursion' % (maxDepth,))
        data = loadJson(filename)
        folder = os.path.dirname(filename)
        try:
            if isinstance(data['inherit'], unicode):
                data['inherit'] = [data['inherit']]
            if not isinstance(data['inherit'], list):
                raise OptionsError('the "inherit" member of an options dictonary is expected to be a (unicode)string or a list of strings. This one was ' + str(type(data['inherit'])) + ' in the file: ' + filename)
            depth += 1
            stack += [(folder + '/' + item, depth) for item in data['inherit']]
            del data['inherit']
        except KeyError:
            #if there is no key "inherit" everything is fine
            pass
        extendInstructions(options, data)
    #add the default values to fill in missing information
    extendInstructions(options, defaults)
    vprint ('loaded instructions:%s' % u''.join([u'\n    %r (%d)' % item for item in loaded]), level = 2)
    return options

def extendInstructions(base, extension):
    """Extend base with extension. Used by loadInstructions."""
    for key,value in extension.iteritems():
        if key in base:
            #we don't update lists or strings or such
            if not isinstance(base[key], dict): continue
            new = {}
            try:
                new.update(value)
                new.update(base[key])
            except ValueError:
                continue
            base[key] = new
        else:
            base[key] = value


class Font(object):
    """a Font is a collection of glyphs and some metadata"""
    glyphs = {}
    data = defaults['font']
    features = {}
    _classes = None
    names = None

    def __init__(self, instructions, names = False):
        self.data.update(instructions['font'])
        self.features = instructions['features']
        self.names = (names or UnicodeAndNames(instructions['name2Unicode']))

    def setGlyph(self, glyphName, charData):
        name = self.names.getName(glyphName)
        if(name in self.glyphs):
            vprint('overwriting:', glyphName, u'({0})'.format(name), 'it already exists.', 'It was called:', self.glyphs[name]['rawName'], 'at load time.', level=2)
        vprint(u'setting Glyph:', glyphName, 'as:', name, level = 3)
        lines,width = self.normalizeCharData(charData)
        self.glyphs[name] = {'lines':lines, 'width':width, 'rawName' : glyphName}

    def __getattr__(self, name):
        """Some lazy processing to return a dict of kerning-classes."""
        if name == 'classes':
            if self._classes is None:
                self._classes = {}
                for k,v in self.features['kerningClasses'].iteritems():
                    self._classes[k] =  map(self.names.nameGetter, v.split(' '))
            return self._classes
        raise AttributeError('%s not found' % (name))

    def getGlyphClasses(self, name):
        """Return a list of the kerning-classes that contain the glyph with name."""
        if '_classes' not in self.glyphs[name]:
            self.glyphs[name]['_classes'] = []
            for k,v in self.classes.iteritems():
                if name in v:
                    self.glyphs[name]['_classes'].append(k)
            if len(self.glyphs[name]['_classes']) > 2:
                vprint('glyph', name, 'has more than 2 classes:', len(self.glyphs[name]['_classes']), self.glyphs[name]['_classes'], level=1)
        return self.glyphs[name]['_classes']

    def getDistances(self, name):
        if '_dist' not in self.glyphs[name]:
            dist = [0,0,0]#[left, right, nirvana]
            for klass in self.getGlyphClasses(name):
                if klass in self.features['distances']:
                    distIndex = -1 #nirvana
                    if klass.startswith(self.data['classLeftIndicator']):
                        distIndex = 0
                    elif klass.startswith(self.data['classRightIndicator']):
                        distIndex = 1
                    dist[distIndex] += self.features['distances'][klass]
            self.glyphs[name]['_dist'] = (dist[0], dist[1])
        return self.glyphs[name]['_dist']

    def normalizeCharData(self, charData):
        """
        Bring a charData in a normal Form

        After normalization all chars will have the same amount of lines: self.data['lineCount'].
        Each line of a char will have the same length: the length of the initially longest line of the char
        filled only with either self.data['filled'] or self.data['empty']

        """
        width = 0
        lines = []
        for line in charData:
            line = u''.join(line.splitlines())
            lineLength = len(line)
            if(lineLength > width):
                width = lineLength
            lines.append(line)
            #if there are to many lines
            if len(lines) == self.data['lineCount']:
                break;
        #if there are to few lines
        lines.extend([u'' for i in range(len(lines), self.data['lineCount'])])
        normal = []
        regex = '[^%s]' % self.data['filled']
        for line in lines:
            #everything that is not self.data['filled'] becomes self.data['empty']
            #every line that length is < width will be filled on the right side with self.data['empty']
            normal.append(re.sub(regex, self.data['empty'], line)\
                .ljust(width, self.data['empty']))
        return (tuple(normal), width)

def fontFromFolder(instructions):
    """Return a Font object from a BMF stored in a folder (which is standard). In fact this only loads the glyph files from disc."""
    font = Font(instructions)
    for glyphName, glyphFile in instructions['glyphs'].iteritems():
        path = '%s/%s/%s' % (font.data['folder'], font.data['glyphFolder'], glyphFile)
        lines = []
        with codecs.open(path, mode='r', encoding='utf-8') as file:
            for line in file:
                lines.append(line)
                if len(lines) == font.data['lineCount']:
                    break;
        font.setGlyph(glyphName, lines)
    return font


class Generator(object):
    """a Generator converts a font into something else, defined by its derived class"""
    font = None
    data = defaults['generator']
    instructions = {}

    def __init__(self, instructions, font):
        self.font = font
        self.data.update(instructions['generator'])
        self.instructions = instructions
        pass

    def generate(self):
        """The generate function is called to run the Generator after it has been set up."""
        raise GeneratorError('a Generator must define a method called generate')

    def __call__(self):
        self.generate()


class KerningClassesGenerator(Generator):
    """Generate qlyph classes for kerning by using a hash of the glyphs edges."""
    words = {}
    _leftEdge = 1
    _rightEdge = 1

    def __init__(self,  instructions, font):
        super(KerningClassesGenerator, self).__init__(instructions, font)
        self.words = {self.font.data['empty'] : u'N', self.font.data['filled'] : u'Y'}

    def __setattr__(self, name, value):
        if name in ('leftEdge', 'rightEdge'):
            value = int(value)
            name = '_' + name
            if value < 1:
               value = 0
        Generator.__setattr__(self, name, value)

    def __getattr__(self, name):
        if name in ('leftEdge', 'rightEdge'):
            return self.__dict__['_' + name]
        raise AttributeError('%s not found' % (name))

    def build(self):
        edges = self.getEdges()
        if len(edges) < 1:
            vprint('Nothing to do.')
            return;
        return self.makeClasses(edges);

    def generate(self):
        result = self.build()
        fileName =  '%s/%s_L%d_R%d_%s' % (settings['outputFolder'], self.font.data['fileName'], self.leftEdge, self.rightEdge, self.data['generatedClassesFile'])
        writeJson(fileName, {'features' : { 'kerningClasses': result }});

    def getEdges(self):
        edges = []
        for (side, width) in (('left', self.leftEdge), ('right', self.rightEdge)):
            if width < 1: continue
            edges.append((side, width))
        return tuple(edges)

    def makeClasses(self, edges):
        classes = {}
        for (side, width) in edges:
            classes[side] = {}
        for name, data in self.font.glyphs.iteritems():
            for (side, width) in edges:
                edge = self._getEdge(data, side, width)
                if edge in classes[side]:
                    classes[side][edge].append(data['rawName'])
                else:
                   classes[side][edge] = [data['rawName']]
        result = {}
        for (side, width) in edges:
            vprint(len(classes[side]), 'classes for ', side, 'edge at width', width, level = 2)
            for edge, chars in classes[side].iteritems():
                result[self._getNameForEdge(side, edge, chars)] = u' '.join(chars);
        return result

    def _getEdge(self, data, side, width):
        """Return a tuple representing the edge of glyph."""
        if side not in ('left', 'right'):
            raise ValueError('side must be either "left" or "right"')
        if data['width'] <= width:
            return tuple(data['lines'])
        edge = []
        if side == 'left':
            for line in data['lines']:
                edge.append(line[0:width])
        if side == 'right':
            for line in data['lines']:
                edge.append(line[data['width']-width:])
        return tuple(edge)

    def _getNameForEdge(self, side, edge, chars):
        sideName = {'left': self.font.data['classLeftIndicator'], 'right': self.font.data['classRightIndicator']}
        return u'%s_%d_%s' % (sideName[side], len(edge[0]), self._getEdgeHash(edge))

    def _getEdgeHash(self, edge):
        """
        Return a hash from edge for the kerning classes, in a way that it stays somehow readable

        N Stand for an empty field, Y for a filled field 8N2YN is from top to bottom 8 fields empty then 2 fields filled then one field empty.
        A X separates colums, if there are more than one.

        It is possible that the name gets too long (for fontforge/postscript) I don't know the exact numbers
        in these cases there should be a simple hashing algorithm that just makes reliable unique names
        of course readabillity of the hash's content would be lost
        """
        trans = []
        for x in xrange(len(edge[0])):
            column = []
            for y in edge:
                column.append(y[x])
            trans.append(column)
        result = []
        for i in xrange(len(trans)):
            current = None
            count = 0;
            for char in trans[i]:
                if char is not current:
                    self._chunker(result, count, current)
                    count = 0;
                    current = char
                count += 1
            self._chunker(result, count, current)
            result.append(u'X')#new column
        #last line needs no columnseparator
        return u''.join(result[0:-1])

    def _chunker(self, result, count, char):
        if count > 1:
            result.append(u'%X%s' % (count, self.words[char]))
        elif count is 1:
            result.append(self.words[char])


class DistancesGenerator(Generator):
    """
    A number is added to the distance value (i.e. left or right side bearing) of a kerning class and removed from all possible kerning partners or vice versa

    This is to reduce kerning pairs, by moving that information to the
    distance table (i.e. left or right side bearing) of a kerning class.
    It is used to achieve more readabillity in environments where kerning
    is not available, while maintaining the same appearance of the font
    where kerning is availabe.

    I needed it, so someone might need it sometimes, too.

    """
    _dist = 0
    _klass = ''
    notate = True

    def __setattr__(self, name, value):
        if name is 'dist':
            value = int(value)
            name = '_' + name
        if name is 'klass':
            if value not in self.font.features['kerningClasses']:
                raise ValueError('classname not found {0}'.format(value))
            elif not self.getSide(value):
                raise ValueError('can\'t determine side of class {0}'.format(value))
            name = '_' + name
        Generator.__setattr__(self, name, value)

    def __getattr__(self, name):
        if name in ('dist', 'klass'):
            return self.__dict__['_' + name]
        raise AttributeError('%s not found' % (name))

    def getSide(self, className):
        sides = (
            ('left', self.font.data['classLeftIndicator'], self.font.data['classRightIndicator'], (0, 1)),
            ('right', self.font.data['classRightIndicator'], self.font.data['classLeftIndicator'], (1, 0))
        )
        side = None
        for side in sides:
            if className.startswith(side[1]):
                break
        return side or False

    def generate(self):
        if not self.alterDistances():
            return
        result = {
            'distances' :   self.font.features['distances'],
            'kern' : self.font.features['kern'],
            'kerningClasses' : self.font.features['kerningClasses'],
        }
        fileName =  '%s/%s_%s' % (settings['outputFolder'], self.font.data['fileName'], self.data['generatedKerningFile'])
        writeJson(fileName, {'features' : result});

    def getPossiblePartners(self):
        """get all possible kerning partners for the class"""
        allPairs = []
        side = self.getSide(self.klass)
        for partner in self.font.features['kerningClasses'].keys():
            if partner is self.klass or not partner.startswith(side[2]): continue
            allPairs.append(partner)
        vprint ('there are', len(allPairs),'possible kerning pairs', level = 2)
        return allPairs

    def getExistingPairs(self):
        """get all existing kerning pairs for the class"""
        existingPairs = {}
        side = self.getSide(self.klass)
        partnerIndex, clsIndex = side[3]
        existingPairs = {}
        for val in self.font.features['kern']:
            if val[clsIndex] != self.klass: continue
            existingPairs[val[partnerIndex]] = val #the whole entry
        vprint ('there are', len(existingPairs),'existing kerning pairs in total', len(self.font.features['kern']), 'pairs', level = 2)
        return existingPairs

    def alterDistances(self):
        side = self.getSide(self.klass)
        if self.dist == 0 or self.klass == '' or side == False:
            vprint('nothing to do')
            return False;
        vprint ('altering', side[0] ,'sided class', self.klass, 'by', self.dist)

        partners = self.getPossiblePartners()
        existingPairs = self.getExistingPairs()
        #the action itself
        #indexes 0 = nothing, 1 = deleted, 2 = added, 3 = altered
        actionVerbs = ('did nothing with','deleted','added','altered')
        actionCount = [0,0,0,0]
        partnerIndex, clsIndex = side[3]
        #what is added to distances will be removed from kern
        changeVal = self.dist * -1
        for partner in partners:
            #build the new pair
            pair = ['','', changeVal]
            pair[partnerIndex] = partner
            pair[clsIndex] = self.klass
            actionIndex = 0
            if partner in existingPairs:
                #add the old kerning value
                pair[2] += existingPairs[partner][2]
                #remove it from the kern table
                self.font.features['kern'].remove(existingPairs[partner])
                actionIndex += 1
                pair += existingPairs[partner][3:]#if there is anyting beyond the standards in this entry
            if pair[2] is not 0:
                #add or re-add it to the kern table
                actionIndex += 2
                self.font.features['kern'].append(pair)
            actionCount[actionIndex] += 1
            vprint (actionVerbs[actionIndex], u', '.join(map(unicode, pair)), 'old value was', changeVal - pair[2], level = 3)
        for verb, count in zip(actionVerbs, actionCount):
            vprint ('%s: %d' % (verb, count), level = 2)
        #remember this change in the distances table!
        newVal = self.font.features['distances'].get(self.klass, 0) + self.dist
        if self.notate:
            if newVal == 0:
                del self.font.features['distances'][self.klass]
                vprint('removed', self.klass, 'from distances, the value is', newVal)
            else:
                self.font.features['distances'][self.klass] = newVal
                vprint('the value of', self.klass, 'in distances is now', newVal)
        else:
            vprint('the new value of', self.klass, newVal, 'is not notated in the distances table')
        return True;


class FontforgeGenerator(Generator):
    """makes a fontforge font (or anything fontforge can generate) from a font"""
    _drawOptions = None

    def __init__(self,  instructions, font):
        super(FontforgeGenerator, self).__init__(instructions, font)
        self.target = fontforge.font()
        self.target.em = self.data['em']
        self._setup()
        self._setupMetadata()

    def _setup(self):
        """set up the fontforge font"""
        #initial setting
        font = self.font
        #seems like there has to be at least one char in the font for the setup
        stub = self.target.createChar(-1, '_stub')
        if self.data['emDescent']:
            descent = int(self.data['emDescent'])
            vprint ('descent, using generator.emDescent:', descent, level = 2)
        else:
            descent = font.data['descent'] * self.data['unit']
            vprint ('descent, calculated from font.descent * generator.unit:', descent, level = 2)
        self.target.ascent = self.data['em'] - descent
        self.target.descent = descent
        self.target.upos = font.data['upos'] * self.data['unit'] + self.data['offset']
        self.target.uwidth = font.data['uwidth'] * self.data['unit'] - (2 * self.data['offset'])
        fontFolder = font.data['folder']
        if  font.data['featureFile']:
            self.target.mergeFeature(u'%s/%s' % (fontFolder, font.data['featureFile']))
            vprint('merged featureFile: %s' % (font.data['featureFile'],), level = 2)
        self.target.removeGlyph(stub)

    @staticmethod
    def _getFeatureScriptLangTuple(featureTag, languageSystems):
        """obscure thing that"""
        return ((
            featureTag,
            tuple([(script, (lang,),) for script, lang in languageSystems])
            ),)

    def addLigatures(self):
        """adding ligatures it is best when the glyphs in the font are already build, right?"""
        for featureTag in ('liga', 'dlig', 'hlig', 'ccmp'):
            if featureTag not in self.font.features or len(self.font.features[featureTag]) < 1: continue
            lookupName = '{0}Ligatures'.format(featureTag)
            subtableName = '{0}Sub 0'.format(lookupName)
            self.target.addLookup(
                lookupName,
                'gsub_ligature',
                (),
                self._getFeatureScriptLangTuple(featureTag, self.font.features['languagesystems'])
            )
            self.target.addLookupSubtable(lookupName, subtableName)
            for sub, by in self.font.features[featureTag]:
                glyphName = self.font.names.getName(by)
                if glyphName not in self.target:
                    glyph = self.target.createChar(*self.font.names.getUnicodeAndName(by))
                    vprint('created', glyphName, '({0})'.format(by),'which is said beeing a ligature for', sub, 'but didn\'t exist until now.', level = 2)
                else:
                    glyph = self.target[glyphName]
                glyph.addPosSub(subtableName, map(self.font.names.nameGetter, sub.split(' ')))

    def addKerning(self):
        featureTag = 'kern'
        lookupName = '{0}Kerning'.format(featureTag)
        subtableName = '{0}Sub 0'.format(lookupName)
        self.target.addLookup(
            lookupName,
            'gpos_pair',
            (),
            self._getFeatureScriptLangTuple(featureTag, self.font.features['languagesystems'])
        )
        firstClasses = tuple(filter(lambda x: x.startswith(self.font.data['classRightIndicator']), self.font.classes.keys()))
        secondClasses = tuple(filter(lambda x: x.startswith(self.font.data['classLeftIndicator']), self.font.classes.keys()))
        pairs = {}
        for pair in self.font.features['kern']:
            pairs[(pair[0], pair[1])] = pair[2]
        #The offsets argument is a tuple of kerning offsets. There must be as many entries as len(first-class)*len(second-class).
        offsets = []
        for f in firstClasses:
            for s in secondClasses:
                offsets.append(self.data['unit'] * pairs.get((f,s),0))
        self.target.addKerningClass(\
            lookupName,\
            subtableName,\
            [self.font.classes[k] for k in firstClasses],\
            [self.font.classes[k] for k in secondClasses],\
            offsets)

    def _setupMetadata(self):
        metadata = self.instructions['metadata']
        target = self.target
        target.fontname = metadata['fontname']
        target.weight = metadata['weight']
        target.fullname = metadata['fullname']
        target.familyname = metadata['familyname']
        target.copyright = metadata['copyright']
        target.version = metadata['version']
        target.comment = metadata['comment']
        for language, data in metadata['more'].iteritems():
            for strid, string in data.iteritems():
                try:
                    target.appendSFNTName(settings['sfntLookup'].get(language, language), settings['sfntLookup'].get(strid, strid), string)
                except TypeError, e:
                    vprint ('some metadata has not been set:', language, strid, 'Message:', e)

    def build(self):
        for name, data in self.font.glyphs.iteritems():
            self.makeChar(name, data)
        self.addLigatures()
        self.addKerning()

    def generate(self):
        self.build();
        for fileExtexsion in self.data['fileFormats']:
            fileName = '%s/%s.%s' % (settings['outputFolder'] , self.font.data['fileName'], fileExtexsion)
            if fileExtexsion is 'sfd':
                self.target.save(fileName)
            else:
                self.target.generate(fileName, flags = self.data['ffGenerateFlags'])
            vprint('wrote a .%s-file: %s' % (fileExtexsion, fileName), level = 1)

    def isFilled(self, val):
        return (val == self.font.data['filled'])

    def getChoord(self, matrix, y, x):
        """Return True if the field at (y, x) is filled, or return False"""
        if y < 0 or x < 0:
            return False
        try:
            return self.isFilled(matrix[y][x])
        except IndexError, e:
            return False

    def getInnerContextualCorners(self, matrix, y, x):
        """
        Find out where to draw rounded corners.

        Return a tuple with four values either True for a rounded corner or False for an angled one.
        Starting at the lower left, going clockwise: (south_west, north_west, north_east, south_east)

        """
        # the function returns a value indicating if the surrounding fields
        # (top, right, bottom, left) of Point x,y (P) are filled(#)
        # ore not(.) there are 2^4 different values, making it fit into one byte
        # thats how it works:
        #     .                            .                            .                            .
        #    .P. is (0, 0, 0, 0) is 0x0   #P. is (0, 0, 0, 1) is 0x1   .P. is (0, 0, 1, 0) is 0x2   #P. is (0, 0, 1, 1) is 0x3
        #     .                            .                            #                            #
        #
        #     .                            .                            .                            .
        #    .P# is (0, 1, 0, 0) is 0x4   #P# is (0, 1, 0, 1) is 0x5   .P# is (0, 1, 1, 0) is 0x6   #P# is (0, 1, 1, 1) is 0x7
        #     .                            .                            #                            #
        #
        #     #                            #                            .                            #
        #    .P. is (1, 0, 0, 0) is 0x8   #P. is (1, 0, 0, 1) is 0x9   #P# is (1, 0, 1, 0) is 0xA   .P# is (1, 0, 1, 1) is 0xB
        #     .                            .                            .                            #
        #
        #     #                            #                            #                            #
        #    .P# is (1, 1, 0, 0) is 0xC   #P# is (1, 1, 0, 1) is 0xD   .P# is (1, 1, 1, 0) is 0xE   #P# is (1, 1, 1, 1) is 0xF
        #     .                            .                            #                            #

        top = self.getChoord(matrix, y-1, x)
        right = self.getChoord(matrix, y, x+1)
        bottom = self.getChoord(matrix, y+1, x)
        left = self.getChoord(matrix, y, x-1)

        code = int(''.join([str(int(pos)) for pos in (top, right, bottom, left)]), 2)
        #SW = south west, NW = north west, NE = north east, SE = south east
        SW = (code in (0x0, 0x4, 0x8, 0xC))
        NW = (code in (0x0, 0x2, 0x4, 0x6))
        NE = (code in (0x0, 0x1, 0x2, 0x3))
        SE = (code in (0x0, 0x1, 0x8, 0x9))
        return (SW, NW, NE, SE)

    def getOuterContextualCorners(self, matrix, y, x):
        """
        Find out where to draw outer rounded corners.

        Return a tuple with four values either True for a rounded corner or False for an angled one.
        Starting at the lower left, going clockwise: (south_west, north_west, north_east, south_east)

        """
        #these are the indexes in env for each checked surrounding field
        #   012
        #   7 3
        #   654
        env = (
            self.getChoord(matrix, y -1, x -1),
            self.getChoord(matrix, y -1, x),
            self.getChoord(matrix, y -1, x + 1),
            self.getChoord(matrix, y, x + 1),
            self.getChoord(matrix, y + 1, x + 1),
            self.getChoord(matrix, y + 1, x),
            self.getChoord(matrix, y + 1, x - 1),
            self.getChoord(matrix, y, x - 1)
        )
        #SW = south west, NW = north west, NE = north east, SE = south east
        SW = (env[5] and env[6] and env[7])#if there is something in env 5 6 and 7 draw a round corner in ther south west
        NW = (env[7] and env[0] and env[1])
        NE = (env[1] and env[2] and env[3])
        SE = (env[3] and env[4] and env[5])
        return (SW, NW, NE, SE)

    def makeChar(self, name, data):
        """Draw the data of name into the glyph of the target."""
        (unicde, name) = self.font.names.getUnicodeAndName(name)
        dist = self.font.getDistances(name)
        glyph = self.target.createChar(unicde, name)
        pen = glyph.glyphPen();
        psY = len(data['lines'])#postscript Y, zero is on the bottom of the grid
        height = len(data['lines']) - 1
        filled = self.isFilled
        for line in data['lines']:
            psY -= 1
            y = height - psY
            for x,val in enumerate(line):
                if filled(val):
                    corners = (True, True ,True ,True)
                    if self.data['contextualShape']:
                        corners = self.getInnerContextualCorners(data['lines'], y, x)
                    self.drawFilled(pen, x + dist[0], psY, corners)
                else:
                    self.drawEmpty(pen, x + dist[0], psY, self.getOuterContextualCorners(data['lines'], y, x))
        pen = None
        glyph.round()
        if self.data['removeOverlap']: glyph.removeOverlap()
        glyph.simplify()
        glyph.width = glyph.vwidth = ( data['width'] + sum(dist) ) * self.data['unit']
        if self.data['autoHint']: glyph.autoHint()
        vprint ('built char with unicode:', glyph.unicode, 'name:', name, 'width:', data['width'], glyph.width, level = 3)

    def _getDrawOptions(self):
        if self._drawOptions is None:
            iW = self.data['width']
            oW = iW if not self.data['invertOutside'] else 2 * self.data['unit'] - iW
            maxR = iW * 0.5#radius
            maxOR= oW * 0.5#radius
            if self.data['outsideCornerRadius'] < 1:
                oR = oW * self.data['outsideCornerRadius']
            else:
                oR = self.data['outsideCornerRadius']
            if oR > maxOR:
                vprint('outsideCornerRadius', oR,'was too big.', 'It is now width/2 (outside width * 0.5):', maxOR)
                oR = maxOR
            if self.data['insideCornerRadius'] < 1:
                iR = iW * self.data['insideCornerRadius']
            else:
                iR = self.data['insideCornerRadius']
            if iR > maxR:
                vprint('insideCornerRadius', iR,'was too big.', 'It is now width/2 (width * 0.5):', maxR)
                iR = maxR
            self._drawOptions = {
                'unit' : self.data['unit'],
                'offset' : self.data['offset'],
                'oOffset' : self.data['offset'] if not self.data['invertOutside'] else -self.data['offset'],
                'descent' :self.font.data['descent'],
                'iW' : iW,#width and height
                'oW' : oW,#outer width and height
                'oR' : oR,#outer radius
                'oL' : oR * kappa, #length outside
                'iR' : iR,#inside radius
                'iL' : iR * kappa, #length inside
            }
        return self._drawOptions

    def drawEmpty(self, pen, posX, posY, corners):
        """Draw outside rounded corners on otherwise empty fields only where they belong."""
        options = self._getDrawOptions()
        unit = options['unit']
        offset = options['oOffset']
        descent = options['descent']
        w = options['oW']
        r = options['oR']
        l = options['oL']

        if r < 1:
            corners = (False, False, False, False)
        #get the start point
        x = posX * unit + offset
        y = posY * unit + offset - descent * unit

        cmd = (
            (
                (x, y),
                (x, y + r),
                ((x, y + r - l), (x + r -l, y), (x + r, y))
            ),
            (
                (x, y + w),
                (x + r, y + w),
                ((x + r - l, y + w), (x, y + w -r + l), (x, y + w - r))
            ),
            (
                (x + w, y + w),
                (x + w, y + w - r),
                ((x + w, y + w -r + l), (x + w - r + l, y + w), (x + w - r, y + w))
            ),
            (
                (x + w, y),
                (x + w - r, y),
                ((x  + w -r + l, y), (x + w, y + r - l), (x + w, y + r))
            )
        )
        for i in xrange(0,4):
            if corners[i]:
                pen.moveTo(cmd[i][0])
                pen.lineTo(cmd[i][1])
                pen.curveTo(*cmd[i][2])
                pen.closePath()

    def drawFilled(self, pen, posX, posY, corners):
        """Draw inside rounded corners only where they belong to."""
        options = self._getDrawOptions()
        unit = options['unit']
        offset = options['offset']
        descent = options['descent']
        w = options['iW']
        r = options['iR']
        l = options['iL']

        if r < 1:
            corners = (False, False, False, False)

        #get the start point
        x = posX * unit + offset
        y = posY * unit + offset - descent * unit

        smooth = (
            (
                (x + r, y),
                ((x + r -l, y), (x , y + r -l), (x, y + r))
            ),
            (
                (x, y + w - r),
                ((x, y + w -r + l), (x + r - l, y + w), (x + r, y + w))
            ),
            (
                (x + w - r, y + w),
                ((x + w - r + l, y + w), (x + w, y + w - r + l), (x + w, y + w - r))
            ),
            (
                (x + w, y + r),
                ((x + w, y + r - l), (x + w - r + l, y), (x + w - r, y))
            ))
        angled = (
            (x, y),
            (x, y + w),
            (x + w, y + w),
            (x + w, y))
        lastPos = None
        for i in xrange(0,4):
            if corners[i]:
                if(i == 0):
                    pen.moveTo(smooth[i][0])
                elif smooth[i][0] is not lastPos:
                    pen.lineTo(smooth[i][0])
                pen.curveTo(*smooth[i][1])
                lastPos = smooth[i][1][2]
            else:
                if(i == 0):
                    pen.moveTo(angled[i])
                else:
                    pen.lineTo(angled[i])
                lastPos = angled[i]
        pen.closePath(); #end the contour
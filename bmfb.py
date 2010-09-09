#!/usr/bin/python
# -*- coding: utf-8 -*-

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

import os
from optparse import OptionParser
import graphicoreBMFB as bmfb

def main():
    parser = OptionParser()
    parser.add_option('-a', '--action',
        action='store', type='string', dest='action', default='font',
        help=' // \n'.join((
            'what action to perform',
            '1. "font": generate a font with FontForge.',
            '2. "classes": generate classes for kerning.',
            '3. dist: A number is added to the distance value (i.e. left or right side bearing) of a kerning class and removed from all possible kerning partners or vice versa. The argument before the json file name of the BMF font MUST be the kerning class to work on.',
            '[default: %default]',
        )))
    parser.add_option('-l', '--left',
        action='store', type='int', dest='left', default=1,
        help='if action is "classes": integer value of the width of the left Edge (seccond kerning classes, later on the right side of a kerning pair) [default: %default]')
    parser.add_option('-r', '--right',
        action='store', type='int', dest='right', default=1,
        help='if action is "classes": integer value of the width of the right Edge (first kerning classes, later on the left side of a kerning pair) [default: %default]')
    parser.add_option('-A', '--add',
        action='store', type='int', dest='add', default=0,
        help='if action is "dist": the integer value to add to the kerning of class  [default: %default]')
    parser.add_option('-R', '--remove',
        action='store', type='int', dest='remove', default=0,
        help='if action is "dist": the integer value to remove from the kerning of class  [default: %default]')
    parser.add_option("-v", "--verbose", dest="verbose", type="int", default=0,
        help="print status messages to stdout, the higher the value the more you get [min: 0, max: none but > 3 was not used now, default: %default]")
    parser.add_option("-q", "--quiet", action="store_true", dest="quiet",
        help="don't print status messages to stdout [default]")

    parser.set_defaults(notate=True, verbose=0, quiet=False)
    (options, args) = parser.parse_args()
    if not options.quiet and options.verbose >= 0:
        bmfb.settings['verbosityLevel'] = options.verbose
    bmfb.vprint('verbosity level', options.verbose)

    try:
        instructions = args[-1]
    except IndexError:
        bmfb.vprint('please specify the instructions json file to work on, use the -h option to see some help', level = 0)
        exit(2)

    bmfb.vprint('function main on', instructions, 'current working directory', os.getcwd(), level = 1)
    instructionsData = bmfb.loadInstructions(instructions)
    # for debugging
    # bmfb.writeJson(settings['outputFolder'] + '/' + 'optionsmerged.jsn', instructionsData)
    folderSource = 'specified in the options-file.'
    if 'folder' not in instructionsData['font']:
        instructionsData['font']['folder'] = os.path.dirname(instructions)
        folderSource = 'the directory of the options-file.'
    bmfb.vprint('the font source folder is:', instructionsData['font']['folder'], 'this was', folderSource, level = 1)

    # g = generator(fontName, './fonts/'+fontName);
    if options.action == 'font':
        bmfb.vprint('generating a font from instructions: …', level = 1)
        font = bmfb.fontFromFolder(instructionsData)
        generator = bmfb.FontforgeGenerator(instructionsData, font)
        generator.generate()
    elif options.action == 'classes':
        bmfb.vprint('generating classes for kerning:','left is', options.left, 'right is', options.right, '…', level = 1)
        font = bmfb.fontFromFolder(instructionsData)
        generator = bmfb.KerningClassesGenerator(instructionsData, font)
        generator.leftEdge = options.left
        generator.rightEdge = options.right
        generator.generate()
    elif options.action == 'dist':
        #remove or add a distance from all kerning pairs of this class
        # reflect this in the dist table
        font = bmfb.Font(instructionsData)
        bmfb.vprint('doing the distances …', level = 1)
        generator = bmfb.DistancesGenerator(instructionsData, font)
        try:
            generator.klass = args[-2]
        except IndexError:
            bmfb.vprint('please specify the kerning class name to work on', level = 0)
            exit(2)
        generator.dist = options.add - options.remove
        generator.generate()
    else:
       bmfb.vprint('No valid action given.', options.action, 'is not an action')
    bmfb.vprint ('OK')
if __name__ == '__main__':
    main()

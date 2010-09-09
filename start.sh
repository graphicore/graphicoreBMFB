#!/bin/bash

for f in `ls ./BMFonts/graphicoreBitmapFont/*.jsn`
do
  echo "Processing $f file..."
  ./bmfb.py "$f"
done

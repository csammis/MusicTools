""" Create an SVG file for drilling the cylinder of a music box """

import argparse
from pathlib import Path
from lib.abc import ParseAbcFile, Rest, MusicObject, Note
from typing import List
import sys
import json
import math
import svgwrite

def gen_svg(music: List[MusicObject], file: Path, dimension_data) -> None:
  music_duration = sum([x.duration for x in music])

  drill_diameter = dimension_data["drills"]["diameter"]
  distance_per_beat = drill_diameter + dimension_data["drills"]["spacing"]
  tape_length = music_duration * distance_per_beat

  total_width = dimension_data["combs"][0]["width"]
  tooth_count = dimension_data["combs"][0]["tooth_count"]
  tooth_width = total_width / tooth_count
  striker_offset = (total_width - (tooth_width * (tooth_count - 1))) / 2

  vertical_offset = dimension_data["drawing"]["vertical_offset"]
  horizontal_offset = dimension_data["drawing"]["horizontal_offset"]

  svg_width = total_width + 5 + horizontal_offset
  svg_height = tape_length + 5 + vertical_offset

  template = svgwrite.Drawing(file, size=(f"{svg_width}mm", f"{svg_height}mm"),
                              viewBox=f"0 0 {svg_width} {svg_height}")

  # Draw a stave with one line for each tooth
  for i in range(tooth_count):
    start_x = striker_offset + (i * tooth_width) + horizontal_offset
    template.add(template.line(start=(start_x,0), end=(start_x, tape_length + vertical_offset),
                               stroke_width="0.1", stroke="black"))

  notes = [n for n in music if n.name.lower() != "rest"]
  def note_value_x(note: Note) -> int:
    return striker_offset + (note.value - min(notes).value) * tooth_width + horizontal_offset

  # Draw a drill mark corresponding to each note
  current_beat = 0
  for i in range(len(music)):
    if music[i].name.lower() != "rest":
      x = note_value_x(music[i])
      y = vertical_offset + (current_beat * distance_per_beat)
      template.add(template.circle(center=(x, y), r=drill_diameter / 2, fill="black"))
    current_beat = current_beat + music[i].duration

  template.save(pretty=True)

if __name__ == "__main__":
  parser = argparse.ArgumentParser(usage="Create an SVG file for drilling the cylinder of a music box")
  parser.add_argument("--tooth-count", default=18, help="The number of teeth on the music box's comb")
  parser.add_argument("--file", help="The input file containing music notation in ABC format", required=True)
  cmdline = parser.parse_args()

  path = Path(cmdline.file)
  input_file = ParseAbcFile(path)
  notes = [n for n in input_file.music if n.name.lower() != "rest"]

  mi = min(notes)
  ma = max(notes)
  scale_range = ma.value - mi.value + 1

  proceed = True
  # Ensure that the selected music can be played on the selected comb
  if scale_range > cmdline.tooth_count:
    print(f"The range of {path.name} ({scale_range} steps) exceeds the comb's tooth count ({cmdline.tooth_count}).")
    print(f"Should we: Proceed anyway, or Cancel")
    choice = input(f"P C --> ")
    if choice.strip().lower() == "c":
      proceed = False
  
  if proceed is False:
    sys.exit()

  script_path = Path(__file__).parent
  data_file_path = script_path.parent.joinpath("data/dimensions.json")
  output_path = path.parent.joinpath(path.stem + ".svg")

  with open(data_file_path, "r") as f:
    dimension_data = json.load(f)

  distance_per_beat = dimension_data["drills"]["diameter"] + dimension_data["drills"]["spacing"]
  while type(input_file.music[0]) is Rest:
    print(f"** Removing {input_file.music[0].duration} beats of rest preceding music")
    input_file.music = input_file.music[1:]
  while type(input_file.music[-1]) is Rest:
    print(f"** Removing {input_file.music[-1].duration} beats of rest following music")
    input_file.music = input_file.music[:-2]
  
  if input_file.music[-1].duration > 1:
    print(f"** Setting final note duration to 1")
    input_file.music[-1].duration = 1
  
  total_duration = sum(x.duration for x in input_file.music)
  tape_length = total_duration * distance_per_beat

  print(f"{path.name} has:")
  print(f"\t...{total_duration} beats")
  print(f"\t...for a tape length of {round(tape_length, 2)} mm")
  diameter_mm = tape_length / math.pi
  print(f"\t...and a minimum cylinder diameter of {round(diameter_mm, 2)} mm / {round(diameter_mm / 25.4, 2)}\"")

  gen_svg(input_file.music, output_path, dimension_data=dimension_data)

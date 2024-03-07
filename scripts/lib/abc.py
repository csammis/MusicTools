from pathlib import Path
import re
from typing import List
from functools import total_ordering

class Accidental():
  def __init__(self, value: str):
    self._value = value
    if value == "_":
      self.value = -1
    elif value == "^":
      self.value = 1
    elif value == "=":
      self.value = 0

  def __repr__(self):
    if self.value == -1:
      return "flat"
    elif self.value == 1:
      return "sharp"
    elif self.value == 0:
      return "natural"
    else:
      return ""
    
class MusicObject:
  def __init__(self, name: str, duration: str = ""):
    self.name = name
    if duration == "":
      self.duration = 1
    else:
      self.duration = int(duration)
    
class Rest(MusicObject):
  def __init__(self, duration: str = ""):
    super().__init__("Rest", duration)

@total_ordering
class Note(MusicObject):
  def __init__(self, name: str, accidental: Accidental = None, duration: str = ""):
    super().__init__(name, duration)
    self.accidental = accidental
    self._update_value()

  def __eq__(self, __other: object) -> bool:
    return self.value == __other.value
  
  def __lt__(self, __other: object) -> bool:
    return self.value < __other.value

  def _update_value(self):
    n = self.name[0]
    # Note values are based on piano key position
    base_notes = ["C", "D", "E", "F", "G", "A", "B", "c", "d", "e", "f", "g", "a", "b"]
    base_values = [40, 42, 44, 45, 47, 49, 51, 52, 54, 56, 57, 59, 61, 63]
    self.value = base_values[base_notes.index(n)]
    # Adjust for staff position
    for c in self.name[1:]:
      if c == ",":
        self.value = self.value - 12
      elif c == "'":
        self.value = self.value + 12
    # Adjust for accidental
    if self.accidental is not None:
      self.value = self.value + self.accidental.value

  def set_accidental(self, accidental):
    self.accidental = accidental
    self._update_value()

  def __repr__(self):
    retval = f"{self.name}"
    if self.accidental is not None:
      retval = retval + f"{self.accidental}"
    if self.duration > 0:
      retval = retval + f"{self.duration}"
    return retval

class InformationField:
  def __init__(self, name: str, value: str):
    self.name = name
    self.value = value

class AbcFile:
  def _propagate_key_signature(self):
    signature = [f.value for f in self.fields if f.name == "K"][0]
    signature = signature[1]
    if len(signature) == 0 or signature[0] != "C":
      # The requirement that the key is C with accidentals is because I'm too lazy and dumb to work out signatures more generally
      raise ValueError("Key signature must be present and must be C with accidentals")
    accidentals = signature.split(" ")
    for a in accidentals[1:]:
      if len(a) != 2:
        continue
      mark = a[0]
      note = a[1].lower()
      for n in self.music:
        if n.name.lower() == note and n.accidental is None:
          n.set_accidental(Accidental(mark))

  def __init__(self, fields: List[InformationField], music: List[MusicObject]):
    self.fields = fields
    self.music = music
    self._propagate_key_signature()

def strip_decorators(content: str) -> str:
  """ Strip out unused constructs from the content """
  # Keep characters from timing constructs (rests, note lengths, ties) and pitches
  content = re.sub("[^a-zA-Z0-9\s\/\-\^_,'=\[\]]", "", content)
  # Normalize spaces
  content = re.sub(" +", " ", content)
  # Join ties with whatever followed after decorators were removed
  content = content.replace("- ", "-")
  return content

def ParseAbcFile(input: Path) -> AbcFile:
  """
  Creates an AbcFile object from the specified path. Raises `ValueError`
  if the file is malformed or is missing required fields.
  """
  with open(input, "r") as f:
    contents = f.readlines()

  if len(contents) == 0:
    raise ValueError("File is empty")

  if contents[0].strip() != "%abc":
    raise ValueError("File does not appear to be an abc notation file (missing header)")

  InformationFieldMatcher = re.compile("([A-Za-z]):(.*)")
  fields:List[InformationField] = [] 

  index = 1
  # Read lines until a non-information field has been read
  for line in contents[1:]:
    line = line.strip()
    if len(line) != 0:
      information_field = InformationFieldMatcher.match(line)
      if information_field is not None:
        fields.append(InformationField(information_field.group(1).upper(), information_field.groups(2)))
      else:
        break
    index = index + 1

  # Validate header contents
  if len(fields) < 3:
    raise ValueError("Tune header must contain at least X:, T:, and K:")
  if fields[0].name != "X" or fields[1].name != "T":
    raise ValueError("Tune header must begin with X: followed by T:")
  if fields[-1].name != "K":
    raise ValueError("Tune header must end with K:")

  music_content = ''.join([s.strip() for s in contents[index:]])
  music_content = strip_decorators(music_content)

  music: List[MusicObject] = []
  detect_tie = False
  detect_chord = False

  for m in re.finditer("""
                       (?P<chord_start>  \[?)            # Is there a chord start?
                       (?P<accidentals>  [\^=_]*?)       # Any number of accidentals
                       (?P<name>         [a-zA-Z][,']?)  # The name of the note with octave markers
                       (?P<duration>      [0-9]?)        # Duration
                       (?P<chord_end>     \]?)           # Is there a chord end?
                       (?P<tie>           -?)            # Is there a tie?
                       """, music_content, flags=re.VERBOSE):
    if len(m.group("accidentals")) > 0:
      accidental = Accidental(m.group("accidentals"))
    else:
      accidental = None
    name = m.group("name")
    duration = m.group("duration")
    if name.lower() in ["z", "x"]:
      music.append(Rest(duration=duration))
    else:
      music.append(Note(name, accidental=accidental, duration=duration))
    
    if detect_tie:
      if music[-2].name == music[-1].name:
        # If two notes with the same name are tied together, add their durations and remove the most recently added one.
        # If the tied notes don't have the same name that's probably malformed but who cares
        music[-2].duration = music[-2].duration + music[-1].duration
        music = music[:-1]
      detect_tie = False

    detect_tie = m.group("tie") != ""

    if detect_chord:
      # If the parser is in the middle of a chord then the duration of the latest note is zeroed out.
      # The note itself remains in the list but it doesn't contribute to overall duration of the tune.
      music[-1].duration = 0
      detect_chord = m.group("chord_end") == ""
    else:
      detect_chord = m.group("chord_start") != ""


  return AbcFile(fields, music)
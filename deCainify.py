import argparse, os, sys

from PIL import Image
import numpy as np

# Define the signature patterns
ico32x32_signature = bytes.fromhex('28 00 00 00 20 00 00 00 40 00 00 00 01 00 08 00')
ico48x48_signature = bytes.fromhex('28 00 00 00 30 00 00 00 60 00 00 00 01 00 08 00')
ico32x32_length = 2216
ico48x48_length = 3752

# for .ico output:
ico_file_header48x48 = bytes.fromhex('00 00 01 00 01 00 30 30 00 00 00 00 00 00 A8 0E 00 00 16 00 00 00')

#very slow version of the sfall's flavor of crc32 (there probably is a short / standard implementation?)
def crc_str(data):
  crc = 0xFFFFFFFF
  polynomial = 0x1EDC6F41
  
  for byte in data:
    crc ^= byte
    for _ in range(8):
      if crc & 1:
        crc = (crc >> 1) ^ polynomial
      else:
        crc >>= 1
    
  return f'0x{crc ^ 0xFFFFFFFF:08x}'

class DeCainify():

  def __init__(self, input_fname):
    with open(input_fname, 'rb') as f:
      data = f.read()
    self.data = bytearray(data)

    self.start_32x32 = self.data.find(ico32x32_signature)
    self.b_icon_32x32 = self.data[self.start_32x32:self.start_32x32+ico32x32_length]
    #self.b_header_32x32 = self.b_icon_32x32[:40]
    self.b_cmap_32x32 = self.b_icon_32x32[40:40+256*4]
    self.b_bmp_32x32  = self.b_icon_32x32[40+256*4:-128]
    self.b_mask_32x32 = self.b_icon_32x32[-128:]

    self.start_48x48 = self.data.find(ico48x48_signature)
    self.b_icon_48x48 = self.data[self.start_48x48:self.start_48x48+ico48x48_length]
    self.b_header_48x48 = self.b_icon_48x48[:40]
    self.b_cmap_48x48 = self.b_icon_48x48[40:40+256*4]
    self.b_bmp_48x48  = self.b_icon_48x48[40+256*4:-384]
    #self.b_mask_48x48 = self.b_icon_48x48[-384:]

    self.crc_32x32 = crc_str(self.b_icon_32x32)
    self.crc_32x32_verified = self.crc_32x32 == '0xe5494664'
    self.crc_48x48 = crc_str(self.b_icon_48x48)
    self.crc_48x48_verified = self.crc_48x48 == '0xfffdfa49'

  def process(self):
    ### 32x32 -> 48:48:
    cmap_32x32 = np.frombuffer(self.b_cmap_32x32, dtype=np.uint8).reshape(256, 4)[:,:3]
    bmp_32x32  = np.frombuffer(self.b_bmp_32x32,  dtype=np.uint8).reshape(32, 32)
    self.mask_32x32 = np.frombuffer(self.b_mask_32x32, dtype=np.uint8).reshape(32, 4)
    self.mask_32x32 = np.unpackbits(self.mask_32x32).reshape(32, -1)
    self.rgb_image_32x32 = cmap_32x32[bmp_32x32] # or is it rbg? or ?

    cmap_48x48 = np.frombuffer(self.b_cmap_48x48, dtype=np.uint8).reshape(256, 4)[:,:3]
    bmp_48x48  = np.frombuffer(self.b_bmp_48x48,  dtype=np.uint8).reshape(48, 48)
    self.rgb_image_48x48 = cmap_48x48[bmp_48x48] # or is it rbg? or ?

    self.resampled_image = Image.fromarray(self.rgb_image_32x32.astype(np.uint8)).resize((48, 48), Image.Resampling.HAMMING)
    self.resampled_mask = np.array(Image.fromarray(self.mask_32x32.astype(np.uint8)).resize((48, 48), Image.NEAREST))
    padded_resampled_mask = np.pad(self.resampled_mask,((0,0),(0,16)),constant_values=1)

    indexed_image = Image.fromarray(np.array(self.resampled_image)).convert('P', palette=Image.ADAPTIVE, colors=256)
    colormap = np.pad(np.array(indexed_image.getpalette()).reshape(-1, 3),((0,0),(0,1)))
    # e.g. nn interp would require this to make palette shape[0] 256
    colormap = np.pad(colormap,((0,256-colormap.shape[0]),(0,0)))

    self.new_b_mask_48x48 = np.packbits(padded_resampled_mask, axis=-1).tobytes()
    self.new_b_bmp_48x48 = np.asarray(indexed_image).tobytes()
    self.new_b_cmap_48x48 = colormap.flatten(order='C').astype('uint8').tobytes()

  def print_mask(self): # print pip boy head mask
    for c in np.flipud(self.resampled_mask): # silly BMP convention
      for r in c:
        print(r,end='')
      print()

  def save_exe(self, output_fname):
    try:
      data = self.data.copy()
      data[self.start_48x48+40:self.start_48x48+40+256*4+48*48+8*48] = self.new_b_cmap_48x48 + self.new_b_bmp_48x48 + self.new_b_mask_48x48
      with open(output_fname, 'wb') as out:
        out.write(data)
      crc = crc_str(data)
      return crc
    except Exception:
      print(Exception)
      return -1

  def save_ico(self, output_fname):
    try:
      data = ico_file_header48x48 + self.b_header_48x48 + self.new_b_cmap_48x48 + self.new_b_bmp_48x48 + self.new_b_mask_48x48
      with open(output_fname, 'wb') as out:
        out.write(data)
      crc = crc_str(data)
      return crc
    except Exception:
      print(Exception)
      return -1

def main():
  print('Fallout2 executable de-Cainify tool. It replaces 48x48 icon with Tim''s face with Vault Boy.\n')

  parser = argparse.ArgumentParser(description="Tool to deCainify FO2 executable.")
  parser.add_argument('--input', type=str, help="Input file [.exe]", required=True)
  parser.add_argument('--output', type=str, help="Output file [.exe or .ico]. Default: [input]_dC.exe")
  parser.add_argument('--overwrite', action='store_true', help="Allow overwriting existing files.")
  parser.add_argument('--ignore', action='store_true', help="Ignore CRC32 checks for the icon data.")
  args = parser.parse_args()

  if not args.input.lower().endswith('.exe'):
    print(f'Input {args.input} is not an .exe.')
    sys.exit()

  if not args.output:
    ext = args.input[-4:]
    args.output = args.input[:-4]+'_dC'+ext
    print(f'No output defined. Using {args.output}.')

  if args.output.lower().endswith('.exe'):
    MODE = 'EXE'
  elif args.output.lower().endswith('.ico'):
    MODE = 'ICO'
  else:
    print(f'Error: output {args.output} does not end with .exe or .ico.')
    sys.exit()
  
  if not args.overwrite and os.path.exists(args.output):
    print(f'Error: {args.output} exists. Use --overwrite to allow overwriting.')
    sys.exit()

  dc = DeCainify(args.input)
  
  if dc.crc_32x32_verified:
    print('32x32 CRC ok')
  else:
    print('32x32 CRC mismatch.')

  if dc.crc_48x48_verified:
    print('48x48 CRC ok')
  else:
    print('48x48 CRC mismatch.')

  if not args.ignore and (not dc.crc_32x32_verified or not dc.crc_48x48_verified):
    print('Use --ignore to ignore CRC checks.')
    sys.exit()

  dc.process()
  dc.print_mask()

  if MODE == 'EXE':
    crc = dc.save_exe(args.output)
    print(f'Extracted data written to EXE file {args.output}')
    print(f'If you use sfall, add CRC to your ddraw.ini (comma separated list): ExtraCRC={crc}')
  else: # 'ICO'
    _ = dc.save_ico(args.output)
    print(f'Extracted data written to ICON file {args.output}')

if __name__ == '__main__':
  main()
import argparse, os, sys

from PIL import Image
import numpy as np
import cv2

# Define the signature patterns
ico32x32_signature = bytes.fromhex('28 00 00 00 20 00 00 00 40 00 00 00 01 00 08 00')
ico48x48_signature = bytes.fromhex('28 00 00 00 30 00 00 00 60 00 00 00 01 00 08 00')
ico32x32_length = 2216
ico48x48_length = 3752

# for .ico output:
ico_file_header48x48 = bytes.fromhex('00 00 01 00 01 00 30 30 00 00 00 00 00 00 A8 0E 00 00 16 00 00 00')

#very slow version of the sfall's flavor of crc32 (there probably is a short / standard implementation?)
def calc_crc(data):
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

  with open(args.input, 'rb') as f:
    data = f.read()
  data = bytearray(data)
  
  start_32x32 = data.find(ico32x32_signature)
  b_icon_32x32 = data[start_32x32:start_32x32+ico32x32_length]    
  #b_header_32x32 = b_icon_32x32[:40]
  b_cmap_32x32 = b_icon_32x32[40:40+256*4]
  b_bmp_32x32  = b_icon_32x32[40+256*4:-128]
  b_mask_32x32 = b_icon_32x32[-128:]

  start_48x48 = data.find(ico48x48_signature)
  b_icon_48x48 = data[start_48x48:start_48x48+ico48x48_length]
  b_header_48x48 = b_icon_48x48[:40]
  #b_cmap_48x48 = b_icon_48x48[40:40+256*4]
  #b_bmp_48x48  = b_icon_48x48[40+256*4:-384]
  #b_mask_48x48 = b_icon_48x48[-384:]

  crc_32x32 = calc_crc(b_icon_32x32)
  print(f'Checking 32x32 icon CRC: {crc_32x32}', end='')
  if crc_32x32 == '0xe5494664':
    print(' ok')
  else:
    print(' CRC 32x32 mismatch.')
  

  crc_48x48 = calc_crc(b_icon_48x48)
  print(f'Checking 48x48 icon CRC: {crc_48x48}', end='')
  if crc_48x48 == '0xfffdfa49':
    print(' ok')
  else:
    print(' CRC 48x48 mismatch.')

  if not args.ignore and (crc_32x32 != '0xe5494664' or crc_48x48 != '0xfffdfa49'):
    print('Use --ignore to ignore CRC checks.')
    sys.exit()

  ### 32x32 -> 48:48:
  cmap = np.frombuffer(b_cmap_32x32, dtype=np.uint8).reshape(256, 4)[:,:3]
  bmp  = np.frombuffer(b_bmp_32x32,  dtype=np.uint8).reshape(32, 32)
  mask = np.frombuffer(b_mask_32x32, dtype=np.uint8).reshape(32, 4)
  mask = np.unpackbits(mask).reshape(32, -1)

  rgb_image = cmap[bmp] # or is it rbg? or ?
  resampled_image = cv2.resize(rgb_image.astype(np.uint8), (48, 48), interpolation=cv2.INTER_AREA)

  resampled_mask = cv2.resize(mask, (48, 48), interpolation=cv2.INTER_NEAREST)
  padded_resampled_mask = np.pad(resampled_mask,((0,0),(0,16)),constant_values=1)
  new_b_mask_48x48 = np.packbits(padded_resampled_mask, axis=-1).tobytes()

  indexed_image = Image.fromarray(resampled_image).convert('P', palette=Image.ADAPTIVE, colors=256)
  colormap = np.pad(np.array(indexed_image.getpalette()).reshape(-1, 3),((0,0),(0,1)))
  # e.g. nn requires this to make palette shape[0] 256
  colormap = np.pad(colormap,((0,256-colormap.shape[0]),(0,0)))
  new_b_bmp_48x48 = np.asarray(indexed_image).tobytes()
  new_b_cmap_48x48 = colormap.flatten(order='C').astype('uint8').tobytes()


  # print pip boy head mask
  for c in np.flipud(resampled_mask): # silly BMP convention
    for r in c:
      print(r,end='')
    print()        

  if MODE == 'EXE':
    data[start_48x48+40:start_48x48+40+256*4+48*48+8*48] = new_b_cmap_48x48 + new_b_bmp_48x48 + new_b_mask_48x48
    with open(args.output, 'wb') as out:
      out.write(data)
    print(f'Extracted data written to EXE file {args.output}')
    with open(args.output,"rb") as f:
      data = f.read()
    print(f'If you use sfall, add CRC to your ddraw.ini (comma separated list): ExtraCRC={calc_crc(data)}')
  else: # 'ICO'
    new_icon = ico_file_header48x48 + b_header_48x48 + new_b_cmap_48x48 + new_b_bmp_48x48 + new_b_mask_48x48
    with open(args.output, 'wb') as out:
      out.write(new_icon)
    print(f'Extracted data written to ICON file {args.output}')

if __name__ == '__main__':
  main()
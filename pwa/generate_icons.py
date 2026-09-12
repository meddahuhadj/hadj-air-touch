import os
import struct
import zlib

def make_png(width, height, color_bg=(9, 12, 21), color_accent=(0, 120, 212)):
    # Create raw RGBA image data
    raw_data = bytearray()
    for y in range(height):
        raw_data.append(0) # Filter type 0 (None)
        for x in range(width):
            # Gradient background with center glow icon mark
            dx = (x - width / 2) / (width / 2)
            dy = (y - height / 2) / (height / 2)
            dist = (dx*dx + dy*dy) ** 0.5
            
            if dist < 0.35:
                # Icon mark 'H' / accent glow
                r, g, b = 0, 229, 255
            elif dist < 0.7:
                # Radial gradient background
                r = int(color_accent[0] * (1 - dist) + color_bg[0] * dist)
                g = int(color_accent[1] * (1 - dist) + color_bg[1] * dist)
                b = int(color_accent[2] * (1 - dist) + color_bg[2] * dist)
            else:
                r, g, b = color_bg
                
            raw_data.extend([r, g, b, 255])

    # PNG chunks
    def chunk(chunk_type, data):
        c_type = chunk_type.encode('ascii')
        crc = zlib.crc32(c_type + data) & 0xffffffff
        return struct.pack('>I', len(data)) + c_type + data + struct.pack('>I', crc)

    header = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    ihdr = chunk('IHDR', ihdr_data)
    idat = chunk('IDAT', zlib.compress(bytes(raw_data)))
    iend = chunk('IEND', b'')

    return header + ihdr + idat + iend

os.makedirs('pwa/icons', exist_ok=True)
with open('pwa/icons/icon-192.png', 'wb') as f:
    f.write(make_png(192, 192))

with open('pwa/icons/icon-512.png', 'wb') as f:
    f.write(make_png(512, 512))

print("PWA Icons generated successfully in pwa/icons/")

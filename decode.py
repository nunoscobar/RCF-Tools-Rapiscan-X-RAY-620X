import struct
import colorsys
import numpy as np
from PIL import Image

def rol8(val, shift):
    return ((val << shift) & 0xFF) | (val >> (8 - shift))

def gerar_imagem_colorida(ch_baixa, ch_alta):
    # Normalizar intensidades pelo fundo claro (ar)
    i_low = np.clip(ch_baixa.astype(np.float32) / (np.percentile(ch_baixa, 99.5) or 1.0), 1e-4, 1.0)
    i_high = np.clip(ch_alta.astype(np.float32) / (np.percentile(ch_alta, 99.5) or 1.0), 1e-4, 1.0)

    # Atenuação logarítmica (lei de Beer-Lambert)
    att_low = -np.log(i_low)
    att_high = -np.log(i_high)

    # Rácio de número atómico efetivo (Z_eff): maior nos metais, menor nos orgânicos
    ratio = att_low / np.maximum(att_high, 1e-3)

    # Mapear rácio para tonalidade HSV (0.08 = Laranja/Orgânico -> 0.33 = Verde/Misto -> 0.62 = Azul/Metal)
    hue = np.clip((ratio - 1.0) / 1.5, 0.0, 1.0) * 0.54 + 0.08

    # Saturação reduzida no fundo vazio (onde quase não há atenuação)
    densidade = np.clip(att_high / (np.percentile(att_high, 99) or 1.0), 0.0, 1.0)
    sat = np.clip(densidade * 3.0, 0.0, 0.92)

    # Luminosidade baseada na transmissão de alta energia (penetrabilidade)
    val = np.clip(i_high ** 0.75, 0.0, 1.0)

    # Converter HSV para RGB
    h, w = ch_baixa.shape
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            r, g, b = colorsys.hsv_to_rgb(float(hue[y, x]), float(sat[y, x]), float(val[y, x]))
            rgb[y, x] = (int(r * 255), int(g * 255), int(b * 255))

    return Image.fromarray(rgb)

def decode_rcf(filepath, out_prefix="saida", width=None):
    with open(filepath, "rb") as f:
        data = f.read()

    marker = b"\x11\x11\xff\xff"
    positions = []
    pos = data.find(marker)
    while pos != -1:
        positions.append(pos)
        pos = data.find(marker, pos + 4)

    raw_pixels = bytearray()

    for i, start in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(data)
        chunk = data[start:end]
        
        chunk_type = struct.unpack_from("<I", chunk, 4)[0]
        
        if chunk_type == 3:
            payload = chunk[28:]
            valid_len = (len(payload) // 4) * 4
            raw_pixels.extend(payload[:valid_len])

    total_pixels = len(raw_pixels) // 4
    print(f"Total de píxeis extraídos: {total_pixels}")

    if width is None:
        larguras_comuns = (944, 1024, 1088, 1152, 896, 960, 1280)
        for w in larguras_comuns:
            if total_pixels % w == 0:
                width = w
                break
        if width is None:
            for w in range(800, 1300):
                if total_pixels % w == 0:
                    width = w
                    break
        if width is None:
            width = 944
            total_pixels = (total_pixels // width) * width
            raw_pixels = raw_pixels[:total_pixels * 4]

    print(f"A usar largura (width) = {width} píxeis (altura = {total_pixels // width} linhas)")

    arr = np.frombuffer(raw_pixels, dtype=np.uint32).reshape((-1, width))

    ch_a = arr & 0xFFFF
    ch_b = (arr >> 16) & 0xFFFF

    ch_a_dec = (rol8((ch_a >> 8).astype(np.uint8), 5).astype(np.uint16) << 8) | (ch_a & 0xFF)
    ch_b_dec = (rol8((ch_b >> 8).astype(np.uint8), 7).astype(np.uint16) << 8) | (ch_b & 0xFF)

    for name, ch in [("baixa_energia", ch_a_dec), ("alta_energia", ch_b_dec)]:
        norm = ((ch - ch.min()) / (np.ptp(ch) or 1) * 255).astype(np.uint8)
        Image.fromarray(norm).save(f"{out_prefix}_{name}.png")

    print("A gerar imagem colorida de discriminação de materiais...")
    img_cor = gerar_imagem_colorida(ch_a_dec, ch_b_dec)
    img_cor.save(f"{out_prefix}_colorida.png")

    print("Conversão concluída com sucesso! Ficheiro gerado: saida_colorida.png")

#decode_rcf("6175146_20261101094531610_3333.RCF")
decode_rcf("6175146_20261101094531610_3333.RCF", out_prefix="6175146_20261101094531610_3333")

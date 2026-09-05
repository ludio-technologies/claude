import urllib.request
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

SRC = {
    "weldon": "https://upload.wikimedia.org/wikipedia/commons/c/ca/Weldon_Spring_letterpress_%28Unsplash%29.jpg",
    "lettres": "https://upload.wikimedia.org/wikipedia/commons/3/33/Lettres_de_bois_%C3%A0_la_brocante_de_L%27Isle-sur-la-Sorgue.jpg",
    "caratteri": "https://upload.wikimedia.org/wikipedia/commons/c/c4/Caratteri_mobili_del_Museo_della_stampa_Lodovico_Pavoni.jpg",
}
for name, url in SRC.items():
    req = urllib.request.Request(url, headers={"User-Agent": "grapheme-asset-fetch/1.0 (ankit@ludio.gg)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        open(f"/tmp/src_{name}.jpg", "wb").write(r.read())
    im = Image.open(f"/tmp/src_{name}.jpg")
    print(name, im.size)
    # small preview
    im.convert("RGB").resize((360, int(360 * im.size[1] / im.size[0]))).save(f"/tmp/prev_{name}.jpg")

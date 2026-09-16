"""In-memory View A renderer."""
from PIL import Image, ImageDraw
def render(pil_image,bbox,config):
 im=pil_image.convert('RGB'); scale=min(1.0,config['view_a']['max_long_edge']/max(im.size)); out=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.LANCZOS); ImageDraw.Draw(out).rectangle([x*scale for x in bbox],outline=tuple(config['view_a']['box_color']),width=config['view_a']['box_width']); return out

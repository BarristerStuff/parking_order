from PIL import Image,ImageDraw
def make(path,bbox,out):
 im=Image.open(path).convert('RGB');im.load();scale=min(1,896/max(im.size)); z=im.resize((round(im.width*scale),round(im.height*scale)),getattr(Image,'Resampling',Image).LANCZOS);ImageDraw.Draw(z).rectangle([x*scale for x in bbox],outline=(255,0,0),width=4);z.save(out,'JPEG',quality=90);return z

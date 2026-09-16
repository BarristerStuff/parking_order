import io,hashlib
from PIL import Image,ImageDraw

def render(image,bbox,max_long_edge=896,jpeg_quality=90):
 x1,y1,x2,y2=map(float,bbox);w=x2-x1;h=y2-y1;W,H=image.size
 crop=(max(0,int(x1-w)),max(0,int(y1-.75*h)),min(W,int(x2+w+0.999999)),min(H,int(y2+.75*h+0.999999)))
 im=image.crop(crop); sx=max_long_edge/max(im.size)
 if sx<1: im=im.resize((round(im.width*sx),round(im.height*sx)),Image.Resampling.LANCZOS)
 scale=im.width/(crop[2]-crop[0]); box=[(x1-crop[0])*scale,(y1-crop[1])*scale,(x2-crop[0])*scale,(y2-crop[1])*scale]
 d=ImageDraw.Draw(im);d.rectangle(box,outline=(255,0,0),width=4)
 b=io.BytesIO();im.save(b,'JPEG',quality=jpeg_quality)
 return b.getvalue(),crop,box

import math
import pdb
from PIL import Image, ImageDraw, ImageFont

def frange(start, end=None, inc=None):
	"A range function, that does accept float increments..."
	if end == None:
		end = start + 0.0
		start = 0.0
		if inc == None:
			inc = 1.0
	L = []
	while 1:
		next = start + len(L) * inc
		if inc > 0 and next >= end:
			break
		elif inc < 0 and next <= end:
			break
		elif inc == 0:
			break
		L.append(next)
	return L

def x_of(r, phi):
	return r * math.cos(phi)

def y_of(r, phi):
	return r * math.sin(phi)

def cartesian(r, phi):
	return (x_of(r, phi), y_of(r, phi))

def _circlize(center, r):
	return [center[0] - r, center[1] - r, center[0] + r, center[1] + r]

def draw_star(draw, peak_count, move_to=(0, 0), rotate_by=0, scale=1):
	step = 360 / peak_count
	for i in frange(math.radians(0), math.radians(360), math.radians(step)):
		start = move_to
		end = list(map(lambda a, b: a + b, cartesian(scale, i + math.radians(rotate_by)), move_to))
		draw.line([tuple(map(int, start)), tuple(map(int, end))], fill='black', width=int(.1 * (scale ** .75)))
		draw.ellipse(list(map(int, _circlize(start, .1 * scale))), fill='black')

def draw_circle(vector, total_count=None, move_to=None, scale=1):
	if not move_to:
		move_to = (1.5 * scale, 1.5 * scale)
	image = Image.new('L', tuple(map(lambda a: int(a + 1.5 * scale), move_to)), color='white')
	draw = ImageDraw.Draw(image)
	draw.ellipse(list(map(int, _circlize(move_to, .01 * scale))), fill='black')
	draw.ellipse(list(map(int, _circlize(move_to, scale))), outline='black', fill=None)
	if not total_count:
		total_count = sum(vector)
	stars = []
	for i, count in enumerate(vector):
		stars += [i + 1] * int(count)
	angles = frange(math.radians(0), math.radians(360), math.radians(360 / total_count))
	if len(angles) < len(stars):
		raise Exception('missing star or angle')
	for i, angle in enumerate(angles):
		if i < len(stars):
			draw_star(
				draw, stars[i],
				move_to=list(map(lambda a, b: a + b, cartesian(scale, angle - math.radians(90)), move_to)),
				scale=min(.4 * (2 * math.pi) / total_count, .7) * scale,
				rotate_by=math.degrees(angle) + 90)
	del draw
	return image

def draw_animated_circles(vectors, filename, is_equ=True):
	total_count = max(map(sum, vectors))
	if is_equ:
		total_count = None
	images = []
	print("Composing animation...\n")
	for i, vector in enumerate(sorted(vectors, key=sum)):
		print("\033[F%3d%%" % int((i/len(vectors))*100))
		images.append(draw_circle(vector, total_count=total_count, scale=350))
	images[0].save(filename, format='GIF', save_all=True, append_images=images[1:], duration=500)

def draw_blended_circles(vectors, filename, is_equ=True):
	total_count = max(map(sum, vectors))
	if is_equ:
		total_count = None
	peek = draw_circle(list(vectors)[0], total_count=total_count, scale=350)
	combined = Image.new('L', peek.size, color='white')
	images = []
	for vector in sorted(vectors, key=sum):
		images.append(draw_circle(vector, total_count=total_count, scale=350))
	print("Combining images...\n")
	for x in range(peek.width):
		for y in range(peek.height):
			print("\033[Fx = %3d%% y = %3d%%" % (int((x/peek.width)*100), int((y/peek.height)*100)))
			pixel = int(sum([image.getpixel((x, y)) for image in images]) / len(images))
			combined.putpixel((x,y), pixel)
	combined.save(filename, format='PNG')

def draw_layed_circles(vectors, filename, is_equ=True):
	total_count = max(map(sum, vectors))
	if is_equ:
		total_count = None
	images = []
	#sorting = lambda v: len(v) - (1 / (sum(v) + 1))
	max_max = max(map(max, vectors))
	sorting = lambda v: ''.join([str(e).rjust(int(math.log10(max_max) + 2), '0') for e in v])
	for vector in sorted(vectors, key=sorting):
		images.append(draw_circle(vector, total_count=total_count, scale=350))
		print(sorting(vector))
	count = int(math.sqrt(len(images)) + 1)
	combined = Image.new('L', (images[0].width * count, images[0].height * count), color='white')
	draw = ImageDraw.Draw(combined)
	font = ImageFont.truetype(font='Pillow/Tests/fonts/FreeMono.ttf', size=35)
	print("Creating side-by-side images...\n")
	for i, image in enumerate(images):
		print("\033[F%3d%%" % int((i/len(images))*100))
		x = i % count
		y = int(i / count)
		combined.paste(image, box=(x * image.width, y * image.height))
		draw.text((x * image.width + image.width / 2, y * image.height + image.height / 2), '%d;%d (%d)' % (x,y,i), font=font)
	combined.save(filename, format='PNG')

if __name__ == '__main__':
	draw_circle([2, 1, 2], total_count=6, scale=1000).save('test.png')

import math
import pdb
from PIL import Image, ImageDraw, ImageFont
import numpy

def gaussian(a, b, c, x):
	if c == 0:
		return a
	else:
		return a * numpy.e ** (-( (x-b) ** 2 / (2*c**2) ))

def values_strip(G_data, width=900, lim=50):
	ys = []
	unit_ys = []
	for x in range(width):
		real_x = (lim / width) * x
		y = 0
		for g in G_data:
			current_y = gaussian(g['alpha'], g['count'] + g['mean_bethas'], g['stddev_bethas'], real_x)
			y += current_y ** 2
		ys.append(y)
		unit_ys.append(gaussian(1, 1+1, 1, real_x) ** 2)
	return ys, unit_ys

def draw_strip(G_data, filename, width=900, height=280, lim=50, margin=15, tick=5, draw=None, x_max=None):
	total_height = height + 2 * margin
	image = Image.new('RGB', (width, total_height), color='white')
	if draw == None:
		draw = ImageDraw.Draw(image)

	ys, unit_ys = values_strip(G_data, width, lim)
	
	if x_max == None:
		x_max = max(ys)
	for x, y in enumerate(ys):
		if x_max == 0:
			value = 0
		else:
			value = (y/x_max)
		shade = 64 + int(value*128)
		line = (x, total_height/2 + int(value*(height/2)), x, total_height/2 - int(value*(height/2)))
		draw.line(
			line,
			fill=(255-int(value*255), int(value*255), 0),
			width=1)

	prev = (0, 0)
	for x, y in enumerate(unit_ys):
		if x_max == 0:
			value = 0
			pre_value = 0
		else:
			value = (y/x_max)
			pre_value = (prev[1]/x_max)
		draw.line(
			(prev[0], total_height/2 + int(pre_value*(height/2)), x, total_height/2 + int(value*(height/2))),
			fill=(0, 0, 0),
			width=3)
		draw.line(
			(prev[0], total_height/2 - int(pre_value*(height/2)), x, total_height/2 - int(value*(height/2))),
			fill=(0, 0, 0),
			width=3)
		prev = (x, y)

	for real_x in range(0, lim, tick):
		x = real_x / (lim / width)
		draw.line(
			(x, margin, x, total_height-margin),
			fill=(0, 0, 0),
			width=1)
		font = ImageFont.truetype("arial.ttf", 32)
		draw.text((x + margin/2, total_height / 2 + margin/2), str(real_x), fill=(0,0,0), font=font)

	image.save(filename, format='PNG')

if __name__ == '__main__':
	draw_strip([{'alpha': 1.0, 'count': 1, 'mean_bethas': 1, 'stddev_bethas': 1}], 'test_unit.png', x_max=1)
	draw_strip([{'alpha': 0, 'count': 0, 'mean_bethas': 0, 'stddev_bethas': 0}], 'test_lonely.png', x_max=1)
	draw_strip([{'alpha': 1.0, 'count': 10, 'mean_bethas': 1, 'stddev_bethas': 1}], 'test_big_count.png', x_max=1)
	draw_strip([{'alpha': 1.0, 'count': 1, 'mean_bethas': 10, 'stddev_bethas': 1}], 'test_big_bmean.png', x_max=1)
	draw_strip([{'alpha': 1.0, 'count': 1, 'mean_bethas': 1, 'stddev_bethas': 10}], 'test_big_bdev.png', x_max=1)
	draw_strip([{'alpha': 1.0, 'count': 1, 'mean_bethas': 1, 'stddev_bethas': 0.1}], 'test_small_bdev.png', x_max=1)
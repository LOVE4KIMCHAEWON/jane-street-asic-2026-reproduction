"""Build the technical paper from Markdown. Requires reportlab only."""
import argparse
from html import escape
from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Preformatted,
                               Table, TableStyle, Image, KeepTogether)

WIDTH = A4[0]-112
INK = colors.HexColor('#173c58')
styles = getSampleStyleSheet()
styles.add(ParagraphStyle('PaperTitle',fontName='Times-Bold',fontSize=17,leading=20,
                         textColor=INK,spaceAfter=12,alignment=TA_CENTER))
styles.add(ParagraphStyle('PaperMeta',fontName='Times-Roman',fontSize=10,leading=13,
                         spaceAfter=7,alignment=TA_CENTER))
styles.add(ParagraphStyle('PaperBody',fontName='Times-Roman',fontSize=10.4,leading=13.6,
                         spaceAfter=7,alignment=TA_JUSTIFY))
styles.add(ParagraphStyle('PaperH2',fontName='Times-Bold',fontSize=12.5,leading=15,
                         textColor=INK,spaceBefore=10,spaceAfter=7,keepWithNext=True))
styles.add(ParagraphStyle('PaperH3',fontName='Times-Bold',fontSize=10.8,leading=13.4,
                         spaceBefore=7,spaceAfter=5,keepWithNext=True))
styles.add(ParagraphStyle('PaperTable',fontName='Times-Roman',fontSize=8.8,leading=11.2))
styles.add(ParagraphStyle('PaperCaption',fontName='Times-Italic',fontSize=9.0,leading=11.5,
                         textColor=colors.HexColor('#444444'),spaceBefore=5,spaceAfter=10))
styles.add(ParagraphStyle('PaperCode',fontName='Courier',fontSize=8.1,leading=10.5,
                         backColor=colors.HexColor('#f4f6f8'),borderPadding=7,
                         spaceBefore=4,spaceAfter=9))


def clean(text):
    return text.replace('\u2011','-').replace('\u2013','-').replace('\u2014','-')


def inline(text):
    text = escape(clean(text))
    codes = []
    def protect_code(match):
        codes.append(match.group(1))
        return 'ZZINLINECODE%dZZ' % (len(codes)-1)
    text = re.sub(r'`([^`]+)`',protect_code,text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)',
                  lambda m: '<link href="%s" color="#173c58">%s</link>'%(m.group(2),m.group(1)),text)
    text = re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',text)
    text = re.sub(r'\*([^*]+)\*',r'<i>\1</i>',text)
    for index, code in enumerate(codes):
        text = text.replace('ZZINLINECODE%dZZ'%index,'<font name="Courier" size="8.5">%s</font>'%code)
    return text


def footer(canvas,doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor('#ccd5dd'))
    canvas.setLineWidth(.4)
    canvas.line(56,43,A4[0]-56,43)
    canvas.setFont('Times-Roman',8)
    canvas.setFillColor(colors.HexColor('#5a6570'))
    canvas.drawString(56,31,'LOVE4KIMCHAEWON | AI-assisted technical report | 13 October 2026')
    canvas.drawRightString(A4[0]-56,31,str(doc.page))
    canvas.restoreState()


def build(source,destination):
    lines = source.read_text(encoding='utf-8').splitlines()
    story = []
    index = 0
    seen_section = False
    while index<len(lines):
        line = lines[index].strip()
        if not line:
            index+=1; continue
        if line.startswith('```'):
            block=[]; index+=1
            while index<len(lines) and not lines[index].startswith('```'):
                block.append(clean(lines[index])); index+=1
            story.append(Preformatted('\n'.join(block),styles['PaperCode']))
            index+=1; continue
        if line.startswith('|'):
            rows=[]
            while index<len(lines) and lines[index].strip().startswith('|'):
                row=[cell.strip() for cell in lines[index].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?',cell.replace(' ','')) for cell in row):
                    rows.append([Paragraph(inline(cell),styles['PaperTable']) for cell in row])
                index+=1
            columns=len(rows[0])
            widths = [WIDTH*.41,WIDTH*.59] if columns==2 else [WIDTH*.18,WIDTH*.29,WIDTH*.18,WIDTH*.35]
            table=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e6edf3')),
                ('VALIGN',(0,0),(-1,-1),'TOP'),
                ('LINEBELOW',(0,0),(-1,0),.7,INK),
                ('LINEBELOW',(0,-1),(-1,-1),.5,colors.HexColor('#aebac5')),
                ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
                ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
            story.extend([Spacer(1,4),table,Spacer(1,3)])
            continue
        if line.startswith('!['):
            match=re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)',line)
            path=(source.parent/match.group(2)).resolve()
            image=Image(str(path))
            max_height = 220 if 'logo' in path.name else 245
            scale=min(WIDTH/image.imageWidth,max_height/image.imageHeight)
            image.drawWidth=image.imageWidth*scale
            image.drawHeight=image.imageHeight*scale
            group=[Spacer(1,4),image]
            index+=1
            while index<len(lines) and not lines[index].strip(): index+=1
            if index<len(lines) and lines[index].strip().startswith('*Figure'):
                group.append(Paragraph(inline(lines[index].strip().strip('*')),styles['PaperCaption']))
                index+=1
            story.append(KeepTogether(group)); continue
        if line.startswith('# '):
            story.append(Paragraph(inline(line[2:]),styles['PaperTitle'])); index+=1; continue
        if line.startswith('## '):
            seen_section=True
            story.append(Paragraph(inline(line[3:]),styles['PaperH2'])); index+=1; continue
        if line.startswith('### '):
            story.append(Paragraph(inline(line[4:]),styles['PaperH3'])); index+=1; continue
        if line.startswith('*Table'):
            story.append(Paragraph(inline(line.strip('*')),styles['PaperCaption'])); index+=1; continue
        paragraph=[line]
        index+=1
        while index<len(lines) and lines[index].strip() and not lines[index].startswith(('#','|','```','![')):
            paragraph.append(lines[index].strip()); index+=1
        style=styles['PaperBody'] if seen_section else styles['PaperMeta']
        story.append(Paragraph(inline(' '.join(paragraph)),style))
    doc=SimpleDocTemplate(str(destination),pagesize=A4,rightMargin=56,leftMargin=56,
                          topMargin=48,bottomMargin=55,
                          title='Reproducible Reverse Engineering of the Jane Street 2026 ASIC Puzzle',
                          author='LOVE4KIMCHAEWON',subject='Technical report: complete reproducibility and Easter-egg audit')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    print('Created',destination)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=Path(__file__).resolve().parent/'paper.md')
    parser.add_argument('--out',type=Path,default=Path(__file__).resolve().parent/'paper.pdf')
    args=parser.parse_args()
    build(args.source.resolve(),args.out.resolve())

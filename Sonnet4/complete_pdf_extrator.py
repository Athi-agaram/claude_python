#!/usr/bin/env python3
"""
Complete PDF Extractor with Sonnet 4 Vision
Extracts content from image-based PDFs and saves to output path.
Outputs structured JSON with key-value pairs for document info, instrument settings,
sample data, standards, and key calculations.
"""

import base64
import json
import fitz  # PyMuPDF
from pathlib import Path
from anthropic import Anthropic
import re

class CompletePDFExtractor:
    """Complete PDF extractor using Sonnet 4 vision"""

    def __init__(self):
        api_key = "YOUR_API_KEY_HERE"
        self.client = Anthropic(api_key=api_key)
        print("✅ Sonnet 4 client initialized with working model")

    def extract_pdf_with_vision(self, pdf_path, output_path="sonnet4_output"):
        """Extract PDF content using Sonnet 4 vision"""
        print(f"🔍 Starting PDF extraction: {pdf_path}")
        Path(output_path).mkdir(exist_ok=True)

        try:
            doc = fitz.open(pdf_path)
            results = {
                "pdf_path": pdf_path,
                "metadata": self.extract_metadata(pdf_path),
                "pages": [],
                "full_content": "",
                "summary": "",
                "structured_data": {}
            }

            print(f"📄 Processing {len(doc)} page(s)...")

            for page_num in range(len(doc)):
                print(f"   Processing page {page_num + 1}...")
                page = doc.load_page(page_num)

                mat = fitz.Matrix(2.5, 2.5)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                img_b64 = base64.b64encode(img_data).decode()

                page_content = self.analyze_page_vision(img_b64, page_num + 1)

                results["pages"].append({
                    "page_number": page_num + 1,
                    "content": page_content,
                    "image_size": len(img_data)
                })

                results["full_content"] += f"\n\n=== PAGE {page_num + 1} ===\n{page_content}"

            doc.close()

            # Generate summary and structured data
            results["summary"] = self.generate_summary(results["full_content"])
            results["structured_data"] = self.parse_page_content_to_json(results["full_content"])

            # Save JSON, TXT, and CSV
            self.save_json(results, pdf_path, output_path)
            self.save_results(results, output_path)

            return results

        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def extract_metadata(self, pdf_path):
        """Extract PDF metadata"""
        try:
            doc = fitz.open(pdf_path)
            metadata = doc.metadata
            doc.close()
            return dict(metadata) if metadata else {}
        except:
            return {}

    def analyze_page_vision(self, img_b64, page_num):
        """Analyze page image with Sonnet 4 vision"""
        prompt = f"""
        Analyze this PDF page image and extract ALL visible content. This is page {page_num}.
        Please extract:
        1. ALL text content (headings, paragraphs, labels, captions, etc.)
        2. Document structure and sections
        3. Tables, lists, and structured data
        4. Numbers, dates, codes, references
        5. Any technical specifications or data
        6. Document title and main topics
        """
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
                        {"type": "text", "text": prompt}
                    ]
                }]
            )
            content = response.content[0].text
            print(f"   ✅ Extracted {len(content)} characters from page {page_num}")
            return content
        except Exception as e:
            print(f"   ❌ Vision analysis failed for page {page_num}: {e}")
            return f"Error analyzing page {page_num}: {str(e)}"

    def generate_summary(self, content):
        if not content or len(content.strip()) < 50:
            return "No substantial content found for summary."
        try:
            prompt = f"""
            Based on this PDF content, provide a comprehensive summary:
            {content[:3000]}
            Include:
            1. Document title and type
            2. Main topics and sections
            3. Key information and data
            4. Document purpose and context
            """
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Summary generation failed: {str(e)}"

    def parse_page_content_to_json(self, page_content):
        data = {
            "document_info": {},
            "instrument_settings": {},
            "instrument_info": {},
            "sample_data": {"standard_curve_wells": [], "control_and_sample_wells": []},
            "standards_table": {"headers": [], "data": []},
            "key_calculation": None,
            "full_content": page_content
        }

        # Document Info
        doc_title = re.search(r"# Document Analysis - (.+)", page_content)
        if doc_title:
            data["document_info"]["title"] = doc_title.group(1).strip()

        title = re.search(r"\*\*Title:\*\* (.+)", page_content)
        if title:
            data["document_info"]["document_title"] = title.group(1).strip()

        qc = re.search(r"QC Verified Protocols/(.+?) - Document Status", page_content)
        if qc:
            data["document_info"]["qc_protocol"] = qc.group(1).strip()

        status = re.search(r"Document Status: (\w+)", page_content)
        if status:
            data["document_info"]["status"] = status.group(1).strip()

        date = re.search(r"\*\*(\d{2}-[A-Za-z]{3}-\d{4} \d{2}:\d{2}:\d{2})\*\*", page_content)
        if date:
            data["document_info"]["date"] = date.group(1)

        # Instrument Settings
        wl_comb = re.search(r"\*\*Wavelength Combination:\*\* (\w+)", page_content)
        if wl_comb:
            data["instrument_settings"]["wavelength_combination"] = wl_comb.group(1)

        # Instrument Info
        instr = re.search(r"\*\*Instrument:\*\* (.+)", page_content)
        if instr:
            data["instrument_info"]["instrument"] = instr.group(1).strip()

        rom = re.search(r"\*\*ROM:\*\* (.+)", page_content)
        if rom:
            data["instrument_info"]["rom"] = rom.group(1).strip()

        start_read = re.search(r"\*\*Start Read:\*\* (.+)", page_content)
        if start_read:
            data["instrument_info"]["start_read"] = start_read.group(1).strip()

        temp = re.search(r"\*\*Mean Temperature:\*\* ([\d\.]+)°C", page_content)
        if temp:
            data["instrument_info"]["mean_temperature"] = temp.group(1) + "°C"

        operator = re.search(r"\*\*Read By:\*\* (.+)", page_content, re.IGNORECASE)
        if operator:
            data["instrument_info"]["operator"] = operator.group(1).strip()

        # Sample Data: Standard Wells (A1-A6)
        stds = re.findall(r"- \*\*(A\d)\*\*: ([\d\.]+) Std - ([\d\.e,]+) \(Reduced: ([\d\.e,]+)\) - Date: ([\d\-: ]+)", page_content)
        for well, conc, val, red, date in stds:
            data["sample_data"]["standard_curve_wells"].append({
                "well": well,
                "concentration": float(conc),
                "fluorescence_value": float(val.replace(',', '')),
                "reduced_value": float(red.replace(',', '')),
                "date": date
            })

        # Control and Sample Wells (B1-B8)
        controls = re.findall(r"- \*\*(B\d)\*\*: (.+?) - (?:(?P<val>[\d\.e,]+) \(Reduced: (?P<red>[\d\.e,]+)\) - Date: (?P<date>[\d\-: ]+)|Date: No Data)", page_content)
        for c in controls:
            well, sample, val, red, date = c
            data["sample_data"]["control_and_sample_wells"].append({
                "well": well,
                "sample_type": sample.strip(),
                "fluorescence_value": float(val.replace(',', '')) if val else None,
                "reduced_value": float(red.replace(',', '')) if red else None,
                "date": date if date else None
            })

        # Standards Table
        table_match = re.search(r"## Standards Table\n(.+?)\n\n", page_content, re.DOTALL)
        if table_match:
            table_lines = table_match.group(1).strip().split("\n")
            headers = [h.strip() for h in table_lines[0].split("|")[1:-1]]
            data["standards_table"]["headers"] = headers
            for line in table_lines[2:]:
                cols = [c.strip() for c in line.split("|")[1:-1]]
                row = {}
                for i, h in enumerate(headers):
                    try:
                        row[h] = float(cols[i].replace(',', ''))
                    except:
                        row[h] = cols[i]
                data["standards_table"]["data"].append(row)

        # Key Calculation
        key_calc = re.search(r"## Key Calculations\n\*\*(.+)\*\*", page_content)
        if key_calc:
            data["key_calculation"] = key_calc.group(1).strip()

        return data

    def save_json(self, results, pdf_path, output_path):
        base_name = Path(pdf_path).stem
        json_file = f"{output_path}/{base_name}_structured.json"
        json_data = results["structured_data"]
        json_data["full_content"] = results["full_content"]
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=4, ensure_ascii=False)
        print(f"💾 Saved structured JSON: {json_file}")
        return json_file

    def save_results(self, results, output_path):
        base_name = Path(results["pdf_path"]).stem
        # TXT
        txt_file = f"{output_path}/{base_name}_extracted_content.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(results['full_content'])
        # CSV
        csv_file = f"{output_path}/{base_name}_structured_data.csv"
        self.save_as_csv(results, csv_file)
        return {"txt": txt_file, "csv": csv_file}

    def save_as_csv(self, results, csv_file):
        import csv
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["category", "field", "value"])
            for key, value in results['structured_data'].items():
                if isinstance(value, dict) or isinstance(value, list):
                    writer.writerow([key, "", json.dumps(value)])
                else:
                    writer.writerow([key, "", str(value)])


def main():
    pdf_path = "pg1.pdf"
    output_path = "sonnet4_output"

    print("🚀 Starting Complete PDF Extraction with Sonnet 4")
    print("=" * 70)

    extractor = CompletePDFExtractor()
    results = extractor.extract_pdf_with_vision(pdf_path, output_path)

    if results:
        print("\n" + "=" * 70)
        print("🎉 EXTRACTION COMPLETE!")
        print("=" * 70)
        print(f"📄 PDF: {pdf_path}")
        print(f"📊 Pages: {len(results['pages'])}")
        print(f"📝 Content: {len(results['full_content'])} characters")
        print(f"📁 Output: {output_path}/")
        print("\n📖 Content Preview:")
        print("-" * 50)
        preview = results['full_content'][:500] + "..." if len(results['full_content']) > 500 else results['full_content']
        print(preview)
    else:
        print("❌ Extraction failed")


if __name__ == "__main__":
    main()




# #!/usr/bin/env python3
# """
# Complete PDF Extractor with Sonnet 4 Vision
# Extracts content from image-based PDFs and saves only full_content_lines as human-readable JSON.
# """

# import base64
# import json
# import fitz  # PyMuPDF
# from pathlib import Path
# from anthropic import Anthropic

# class CompletePDFExtractor:
#     """Complete PDF extractor using Sonnet 4 vision"""
    
#     def __init__(self):
#         api_key = "your-api-key"
#         self.client = Anthropic(api_key=api_key)
#         print("✅ Sonnet 4 client initialized with working model")
    
#     def extract_pdf_with_vision(self, pdf_path, output_path="sonnet4_output"):
#         """Extract PDF content using Sonnet 4 vision"""
#         print(f"🔍 Starting PDF extraction: {pdf_path}")
#         Path(output_path).mkdir(exist_ok=True)
        
#         try:
#             doc = fitz.open(pdf_path)
#             full_content = ""

#             print(f"📄 Processing {len(doc)} page(s)...")
            
#             for page_num in range(len(doc)):
#                 print(f"   Processing page {page_num + 1}...")
#                 page = doc.load_page(page_num)
                
#                 # Convert page to high-quality image
#                 mat = fitz.Matrix(2.5, 2.5)
#                 pix = page.get_pixmap(matrix=mat)
#                 img_b64 = base64.b64encode(pix.tobytes("png")).decode()
                
#                 # Analyze page
#                 page_content = self.analyze_page_vision(img_b64, page_num + 1)
#                 full_content += f"\n\n=== PAGE {page_num + 1} ===\n{page_content}"
            
#             doc.close()
            
#             # Split into lines
#             full_content_lines = full_content.splitlines()
            
#             # Save JSON with only full_content_lines
#             self.save_json(full_content_lines, pdf_path, output_path)
#             return full_content_lines
            
#         except Exception as e:
#             print(f"❌ Error: {e}")
#             return None
    
#     def analyze_page_vision(self, img_b64, page_num):
#         """Analyze page image with Sonnet 4 vision"""
#         prompt = f"""
#         Extract all visible text content from this PDF page image (page {page_num}) 
#         including headings, paragraphs, tables, numbers, dates, codes, references, etc.
#         """
#         try:
#             response = self.client.messages.create(
#                 model="claude-sonnet-4-20250514",
#                 max_tokens=4000,
#                 messages=[{
#                     "role": "user",
#                     "content": [
#                         {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
#                         {"type": "text", "text": prompt}
#                     ]
#                 }]
#             )
#             content = response.content[0].text
#             print(f"   ✅ Extracted {len(content)} characters from page {page_num}")
#             return content
#         except Exception as e:
#             print(f"   ❌ Vision analysis failed for page {page_num}: {e}")
#             return f"Error analyzing page {page_num}: {str(e)}"
    
#     def save_json(self, full_content_lines, pdf_path, output_path):
#         """Save only full_content_lines as human-readable JSON"""
#         base_name = Path(pdf_path).stem
#         json_file = f"{output_path}/{base_name}_full_content_lines.json"
#         with open(json_file, "w", encoding="utf-8") as f:
#             json.dump(full_content_lines, f, indent=4, ensure_ascii=False)
#         print(f"💾 Saved human-readable JSON: {json_file}")
#         return json_file


# def main():
#     pdf_path = "pg1.pdf"
#     output_path = "sonnet4_output"
    
#     print("🚀 Starting PDF Extraction")
#     extractor = CompletePDFExtractor()
#     full_content_lines = extractor.extract_pdf_with_vision(pdf_path, output_path)
    
#     if full_content_lines:
#         print(f"🎉 Extraction complete! Lines extracted: {len(full_content_lines)}")
#     else:
#         print("❌ Extraction failed")


# if __name__ == "__main__":
#     main()

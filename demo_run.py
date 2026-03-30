#!/usr/bin/env python3
"""
demo_run.py – Chạy thử toàn bộ pipeline với dữ liệu mẫu.
Không cần tài khoản LinkedIn.
"""
import sys
sys.path.insert(0, "/home/baobao/Projects/Linkin_Compapy")

from company_detail import CompanyDetail
import exporter

# ── Dữ liệu mẫu 15 công ty toàn cầu ─────────────────────────────────────────
SAMPLE_COMPANIES = [
    CompanyDetail(
        name="Stripe",
        linkedin_url="https://www.linkedin.com/company/stripe/",
        website="https://stripe.com",
        industry="Financial Services",
        company_size="1,001-5,000 employees",
        headquarters="South San Francisco, California",
        founded="2010",
        specialties="payments, online payments, financial infrastructure",
        description="Stripe is a financial infrastructure platform for businesses.",
        followers="389,412",
    ),
    CompanyDetail(
        name="Figma",
        linkedin_url="https://www.linkedin.com/company/figma/",
        website="https://figma.com",
        industry="Computer Software",
        company_size="501-1,000 employees",
        headquarters="San Francisco, California",
        founded="2012",
        specialties="design, prototyping, collaboration, UI/UX",
        description="Figma is a collaborative interface design tool.",
        followers="192,781",
    ),
    CompanyDetail(
        name="Grab",
        linkedin_url="https://www.linkedin.com/company/grab/",
        website="https://grab.com",
        industry="Internet",
        company_size="5,001-10,000 employees",
        headquarters="Singapore",
        founded="2012",
        specialties="ride-hailing, food delivery, fintech, logistics",
        description="Grab is the leading superapp platform in Southeast Asia.",
        followers="441,002",
    ),
    CompanyDetail(
        name="Revolut",
        linkedin_url="https://www.linkedin.com/company/revolut/",
        website="https://revolut.com",
        industry="Financial Services",
        company_size="10,001+ employees",
        headquarters="London, United Kingdom",
        founded="2015",
        specialties="neobank, fintech, payments, crypto",
        description="Revolut is a global neobank.",
        followers="275,900",
    ),
    CompanyDetail(
        name="Notion",
        linkedin_url="https://www.linkedin.com/company/notionhq/",
        website="https://notion.so",
        industry="Computer Software",
        company_size="201-500 employees",
        headquarters="San Francisco, California",
        founded="2016",
        specialties="productivity, notes, wikis, databases, project management",
        description="Notion is the all-in-one workspace for your notes, tasks, wikis, and databases.",
        followers="267,543",
    ),
    CompanyDetail(
        name="ByteDance",
        linkedin_url="https://www.linkedin.com/company/bytedance/",
        website="https://bytedance.com",
        industry="Internet",
        company_size="10,001+ employees",
        headquarters="Beijing, China",
        founded="2012",
        specialties="AI, content platform, TikTok, social media",
        description="ByteDance is a technology company that builds AI-driven content platforms.",
        followers="988,123",
    ),
    CompanyDetail(
        name="Shopify",
        linkedin_url="https://www.linkedin.com/company/shopify/",
        website="https://shopify.com",
        industry="Computer Software",
        company_size="10,001+ employees",
        headquarters="Ottawa, Ontario",
        founded="2004",
        specialties="ecommerce, retail, payments, logistics",
        description="Shopify is a commerce platform that allows anyone to start and grow a business.",
        followers="712,004",
    ),
    CompanyDetail(
        name="Klarna",
        linkedin_url="https://www.linkedin.com/company/klarna/",
        website="https://klarna.com",
        industry="Financial Services",
        company_size="5,001-10,000 employees",
        headquarters="Stockholm, Sweden",
        founded="2005",
        specialties="buy now pay later, BNPL, payments, ecommerce",
        description="Klarna is a Swedish fintech company offering payment solutions.",
        followers="223,107",
    ),
    CompanyDetail(
        name="Canva",
        linkedin_url="https://www.linkedin.com/company/canva/",
        website="https://canva.com",
        industry="Computer Software",
        company_size="1,001-5,000 employees",
        headquarters="Surry Hills, New South Wales",
        founded="2012",
        specialties="graphic design, visual communication, SaaS",
        description="Canva is a visual communication platform.",
        followers="504,381",
    ),
    CompanyDetail(
        name="UiPath",
        linkedin_url="https://www.linkedin.com/company/uipath/",
        website="https://uipath.com",
        industry="Computer Software",
        company_size="5,001-10,000 employees",
        headquarters="New York, New York",
        founded="2005",
        specialties="RPA, automation, AI, enterprise software",
        description="UiPath is a leading enterprise automation software company.",
        followers="332,441",
    ),
    CompanyDetail(
        name="VNG Corporation",
        linkedin_url="https://www.linkedin.com/company/vng-corporation/",
        website="https://vng.com.vn",
        industry="Internet",
        company_size="1,001-5,000 employees",
        headquarters="Ho Chi Minh City, Vietnam",
        founded="2004",
        specialties="gaming, fintech, cloud, messaging, entertainment",
        description="VNG is Vietnam's leading technology company.",
        followers="88,521",
    ),
    CompanyDetail(
        name="MoMo",
        linkedin_url="https://www.linkedin.com/company/momovietnam/",
        website="https://momo.vn",
        industry="Financial Services",
        company_size="1,001-5,000 employees",
        headquarters="Ho Chi Minh City, Vietnam",
        founded="2010",
        specialties="e-wallet, fintech, payments, Vietnam",
        description="MoMo is Vietnam's largest mobile payment platform.",
        followers="62,004",
    ),
    CompanyDetail(
        name="N26",
        linkedin_url="https://www.linkedin.com/company/n26/",
        website="https://n26.com",
        industry="Financial Services",
        company_size="1,001-5,000 employees",
        headquarters="Berlin, Germany",
        founded="2013",
        specialties="neobank, mobile banking, fintech, Europe",
        description="N26 is a mobile bank for everyone.",
        followers="145,632",
    ),
    CompanyDetail(
        name="Nubank",
        linkedin_url="https://www.linkedin.com/company/nubank/",
        website="https://nubank.com.br",
        industry="Financial Services",
        company_size="10,001+ employees",
        headquarters="São Paulo, Brazil",
        founded="2013",
        specialties="neobank, credit card, fintech, Latin America",
        description="Nubank is the world's largest digital banking platform.",
        followers="587,221",
    ),
    CompanyDetail(
        name="Wise",
        linkedin_url="https://www.linkedin.com/company/wise/",
        website="https://wise.com",
        industry="Financial Services",
        company_size="5,001-10,000 employees",
        headquarters="London, United Kingdom",
        founded="2011",
        specialties="international money transfer, fintech, FX, payments",
        description="Wise is a global payments technology company.",
        followers="198,443",
    ),
]

# ── Chạy export ───────────────────────────────────────────────────────────────
def main():
    print("\n" + "="*60)
    print("  LinkedIn Company Scraper – Demo Run")
    print("="*60)
    print(f"  Đang xuất {len(SAMPLE_COMPANIES)} công ty mẫu...\n")

    records = [c.to_dict() for c in SAMPLE_COMPANIES]

    exporter.save_csv(records)
    exporter.save_json(records)
    exporter.save_excel(records)

    print("\n" + "="*60)
    print("  KẾT QUẢ MẪU (5 công ty đầu):")
    print("="*60)
    for c in SAMPLE_COMPANIES[:5]:
        print(f"  {c.name:<20} | {c.website:<35} | {c.headquarters}")
    print("  ...")
    print(f"\n  Tổng: {len(SAMPLE_COMPANIES)} công ty")
    print("  Output: output/companies.csv | companies.json | companies.xlsx")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()

🚀 Features
Sales Tracker

Track sales enquiries from initial contact to award
Status management (Pending, Awarded, Rejected)
Search and filter by job number or location
Smart sorting for job numbers
Automatic synchronization with Monthly Awards

Monthly Awards

View awarded jobs organized by month and year
Year/month navigation (2020 to current year +1)
Bidirectional sync with Sales Tracker
Link to sales enquiries or create standalone awards
Track total value per month

Invoiced Jobs

Detailed invoice breakdown by department
Automatic PSL value calculation (Total - Contractor)
Track invoiced vs pending jobs
Value breakdown: Utility, CAD, Topo, Contractor
Warning system for value mismatches
Monthly reporting with totals

📊 System Architecture
Sales Enquiry → Monthly Award → Invoiced Job
     (📊)            (🏆)           (💰)
Data Flow

Sales Enquiry created with status "Pending"
Status changed to "Awarded" → Auto-creates Monthly Award + Invoiced Job
Edit Monthly Award → Syncs with Sales Enquiry
Edit Invoiced Job → Update invoice breakdown
Delete Monthly Award → Reverts Sales status to "Pending"

🛠️ Technology Stack

Backend: Django 5.2.7
Database: PostgreSQL 15
Server: Gunicorn + Nginx
Containerization: Docker & Docker Compose
CI/CD: GitHub Actions
Hosting: AWS EC2

📋 Prerequisites

Python 3.11+
PostgreSQL 15+
Docker & Docker Compose (for deployment)
Git

🔧 Installation
Local Development Setup

Clone the repository:

bashgit clone https://github.com/macdrap/psl_app_django.git
cd psl-workflow-system

Create virtual environment:

bashpython -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

Install dependencies:

bashpip install -r requirements.txt

Create .env file:

bashcp .env.example .env
# Edit .env with your settings

Run migrations:

bashpython manage.py migrate

Create superuser:

bashpython manage.py createsuperuser

Run development server:

bashpython manage.py runserver
Visit: http://127.0.0.1:8000
Docker Development Setup

Build and run:

bashdocker-compose up --build

Create superuser:

bashdocker-compose exec web python manage.py createsuperuser
Visit: http://localhost:8000
🚀 Deployment
AWS EC2 Deployment
See AWS_DEPLOYMENT.md for complete deployment guide.
Quick Deploy:

Launch EC2 instance (t2.micro)
Install Docker
Clone repository
Set environment variables
Run: docker-compose -f docker-compose.prod.yml up -d --build

Automated Deployment
Push to main branch triggers automatic deployment via GitHub Actions:
bashgit add .
git commit -m "Your changes"
git push origin main
📁 Project Structure
psl_app_project/
├── dashboard/              # Sales Tracker app
│   ├── models.py          # SalesEnquiry model
│   ├── views.py
│   ├── forms.py
│   └── templates/
├── monthly_awards/         # Monthly Awards app
│   ├── models.py          # MonthlyAward model
│   ├── views.py
│   ├── forms.py
│   └── templates/
├── invoiced_jobs/          # Invoiced Jobs app
│   ├── models.py          # InvoicedJob model
│   ├── views.py
│   ├── forms.py
│   └── templates/
├── templates/              # Global templates
│   ├── base.html
│   └── login.html
├── static/                 # Static files
├── docker/                 # Docker configuration
├── nginx/                  # Nginx configuration
├── scripts/                # Deployment scripts
└── psl_app_project/       # Django project settings
    ├── settings.py
    ├── urls.py
    └── wsgi.py
💾 Database Schema
SalesEnquiry

job_number (CharField)
date (DateField)
value (DecimalField)
location (TextField)
client / client_contact
email / phone (optional)
status (Pending/Awarded/Rejected)

MonthlyAward

Links to SalesEnquiry (optional)
Inherits all sales data
date (Award date, different from sales date)

InvoicedJob

Links to MonthlyAward (required)
date (Invoice date)
Value breakdown:

utility_value
cad_value
topo_value
contractor_value
psl_value (auto-calculated)


status (Pending/Invoiced)

🔑 Key Features
Bidirectional Sync

Edit Sales Enquiry → Updates Monthly Award
Edit Monthly Award → Updates Sales Enquiry
Delete Monthly Award → Reverts Sales status

Auto Calculations

PSL Value = Total Award Value - Contractor Value
Value mismatch warnings
Monthly totals (invoiced vs pending)

Smart Sorting

Job numbers sorted as version numbers
9999.10 comes before 9999.2 (10 > 2)
Handles both numeric and text job numbers

📊 Version History
Version 1.0.0 (Current)

✅ Sales Tracker with CRUD operations
✅ Monthly Awards with month/year navigation
✅ Invoiced Jobs with breakdown tracking
✅ Bidirectional synchronization
✅ Automatic PSL calculation
✅ Value mismatch warnings
✅ Docker deployment ready
✅ GitHub Actions CI/CD

🔒 Security

Environment variables for sensitive data
CSRF protection enabled
SQL injection protection (Django ORM)
XSS protection
Secure password hashing
Login required for all operations

📝 Environment Variables
See .env.example for required environment variables:
bashSECRET_KEY=          # Django secret key
DEBUG=               # True/False
DB_NAME=             # Database name
DB_USER=             # Database user
DB_PASSWORD=         # Database password
DB_HOST=             # Database host
DB_PORT=             # Database port (default: 5432)
ALLOWED_HOSTS=       # Comma-separated allowed hosts
🧪 Testing
bash# Run tests (to be implemented)
python manage.py test

# Check code coverage
coverage run --source='.' manage.py test
coverage report
📈 Monitoring
View Logs
bash# Docker logs
docker-compose -f docker-compose.prod.yml logs -f

# Django logs
tail -f logs/django.log
Database Backup
bashdocker-compose -f docker-compose.prod.yml exec db pg_dump -U postgres dbname > backup.sql
🤝 Contributing

Create a feature branch
Make your changes
Test thoroughly
Submit a pull request

📞 Support
For issues or questions, please contact the development team.
📄 License
Private - All Rights Reserved
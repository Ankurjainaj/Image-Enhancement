#!/bin/bash
# Initialize database and create tables
# Run this once to set up the MySQL database for the Image Enhancement pipeline

cd "$(dirname "$0")" || exit 1

# Check if database credentials are set
if [ -z "$MYSQL_HOST" ]; then
    echo "⚠️  MySQL credentials not set"
    echo "Please set the following environment variables:"
    echo "  export MYSQL_HOST=localhost"
    echo "  export MYSQL_PORT=3306"
    echo "  export MYSQL_DATABASE=image_enhancer"
    echo "  export MYSQL_USER=root"
    echo "  export MYSQL_PASSWORD=your_password"
    echo ""
    echo "Or create a .env file with these values"
    exit 1
fi

# Initialize database
echo "📊 Initializing database..."
python3 -c "
import sys
sys.path.insert(0, '.')
from src.database import init_db
try:
    init_db()
    print('✅ Database tables created successfully!')
except Exception as e:
    print(f'❌ Error: {e}')
    sys.exit(1)
"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Database initialization complete!"
    echo ""
    echo "📝 Next steps:"
    echo "1. Make sure S3_BUCKET is set: export S3_BUCKET=your-bucket-name"
    echo "2. Make sure AWS credentials are set: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY"
    echo "3. Start the API: uvicorn api.main:app --reload --port 8000"
    echo "4. Start the dashboard: streamlit run dashboard/app.py"
else
    echo "❌ Database initialization failed!"
    exit 1
fi

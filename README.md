# Django Attendance System

A real-time attendance management system built with Django, featuring WebSocket support for live updates and Celery for background task processing.

## Features

- **Real-time Attendance Tracking**: Live updates using Django Channels and WebSockets
- **Background Task Processing**: Celery integration for handling time-consuming operations
- **Modern Web Interface**: Responsive design with real-time data updates
- **Database Integration**: SQLite for development, PostgreSQL ready for production
- **Deployment Ready**: Configured for Render.com deployment

## Technology Stack

- **Backend**: Django 5.1.6
- **Real-time**: Django Channels with WebSocket support
- **Task Queue**: Celery with Redis
- **Database**: SQLite (development), PostgreSQL (production)
- **Deployment**: Render.com
- **CI/CD**: GitHub Actions

## Installation

### Prerequisites
- Python 3.12+
- Redis server
- Git

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/attendance-system.git
   cd attendance-system
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the root directory:
   ```env
   SECRET_KEY=your-secret-key-here
   DEBUG=True
   REDIS_URL=redis://localhost:6379/0
   DATABASE_URL=sqlite:///db.sqlite3
   ```

5. **Run database migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

7. **Start Redis server**
   ```bash
   # On Windows (if installed via Chocolatey)
   redis-server
   
   # On macOS (if installed via Homebrew)
   brew services start redis
   
   # On Linux
   sudo systemctl start redis
   ```

8. **Start Celery worker**
   ```bash
   celery -A attandance_app_mul worker --loglevel=info
   ```

9. **Start the development server**
   ```bash
   python manage.py runserver
   ```

10. **Access the application**
    - Web interface: http://localhost:8000
    - Admin panel: http://localhost:8000/admin

## Deployment

### Render.com Deployment

This project is configured for easy deployment on Render.com:

1. **Fork this repository**
2. **Connect to Render.com**
3. **Create a new Web Service**
4. **Configure environment variables**:
   - `SECRET_KEY`: Generate a secure secret key
   - `DEBUG`: Set to `False`
   - `ALLOWED_HOSTS`: Set to your domain
   - `REDIS_URL`: Add Redis service URL
   - `DATABASE_URL`: Add PostgreSQL database URL

The `render.yaml` file contains the deployment configuration.

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Django secret key | Yes |
| `DEBUG` | Debug mode | Yes |
| `ALLOWED_HOSTS` | Allowed hostnames | Yes |
| `REDIS_URL` | Redis connection URL | Yes |
| `DATABASE_URL` | Database connection URL | Yes |

## Project Structure

```
attdance_system/
├── attandance_app/          # Main Django app
│   ├── models.py           # Database models
│   ├── views.py            # View functions
│   ├── urls.py             # URL routing
│   ├── consumers.py        # WebSocket consumers
│   ├── templates/          # HTML templates
│   └── migrations/         # Database migrations
├── attandance_app_mul/     # Django project settings
│   ├── settings.py         # Django settings
│   ├── urls.py             # Main URL configuration
│   ├── asgi.py             # ASGI configuration
│   └── celery.py           # Celery configuration
├── requirements.txt        # Python dependencies
├── render.yaml            # Render.com deployment config
└── .github/workflows/     # GitHub Actions CI/CD
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

If you encounter any issues or have questions, please open an issue on GitHub.

## Acknowledgments

- Django community for the excellent framework
- Django Channels for WebSocket support
- Celery for background task processing

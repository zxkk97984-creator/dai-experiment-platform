c = get_config()

# Allow iframe embedding from frontend dev server (all localhost ports)
c.ServerApp.tornado_settings = {
    'headers': {
        'Content-Security-Policy': "frame-ancestors http://localhost:* http://127.0.0.1:*; report-uri /api/security/csp-report"
    }
}

# Disable token authentication (already set via command line)
# c.ServerApp.token = ''
# c.ServerApp.password = ''

# Allow all origins for CORS
c.ServerApp.allow_origin = '*'
c.ServerApp.allow_remote_access = True

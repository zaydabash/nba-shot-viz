# Security Policy

## Supported Versions

We actively maintain and provide security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 2.0.x   | :white_check_mark: |
| 1.0.x   | :x:                |

## Security Best Practices

### Credential Management
- **Never commit secrets**: All API keys, credentials, and sensitive data must be stored in `.streamlit/secrets.toml` (gitignored) or environment variables
- **Use environment variables**: For production deployments, use environment variables instead of files
- **Rotate credentials regularly**: Update API headers and credentials periodically
- **Limit access**: Only grant access to secrets to authorized personnel

### Input Validation
- All user inputs are validated and sanitized before processing
- Player names are validated against expected formats
- Season strings are validated against the format (YYYY-YY)
- File paths are constructed using safe path utilities to prevent directory traversal attacks

### Secure Configuration
- All external API calls use HTTPS only
- No hardcoded credentials in source code
- Secure file handling using pathlib
- Comprehensive error handling to prevent information leakage

### Code Security
- No dynamic code execution (eval, exec, compile)
- No insecure HTTP endpoints
- All file operations validate paths
- Input validation on all user inputs

## Reporting a Vulnerability

If you discover a security vulnerability, please do the following:

1. **Do not** open a public GitHub issue
2. Email security concerns to the repository maintainer
3. Provide a detailed description of the vulnerability
4. Include steps to reproduce the issue
5. Suggest a fix if possible

We will respond to security reports within 48 hours and provide a timeline for fixes.

## Security Audit Checklist

Before deploying, ensure:

- [ ] No credentials in source code
- [ ] All secrets are gitignored
- [ ] Environment variables are used for sensitive data
- [ ] Input validation is enabled
- [ ] HTTPS is used for all external calls
- [ ] Error messages don't leak sensitive information
- [ ] File paths are validated
- [ ] No eval() or exec() calls
- [ ] Dependencies are up to date
- [ ] Security scanning tools are run (bandit, safety)

## Automated Security Scanning

This project uses automated security scanning:

- **Bandit**: Static analysis for common security issues
- **Safety**: Checks for known security vulnerabilities in dependencies
- **GitHub Actions**: Automated security scanning on every push

Run security scans locally:

```bash
# Run Bandit security scan
bandit -r src/ app.py

# Check for known vulnerabilities
safety check
```

## Dependency Security

- All dependencies are pinned to specific versions
- Regular dependency updates are performed
- Security vulnerabilities are addressed promptly
- Dependencies are scanned with `safety` before deployment

## Data Privacy

- No personal data is collected or stored
- All data is publicly available NBA statistics
- No user tracking or analytics
- Data is cached locally and not shared externally


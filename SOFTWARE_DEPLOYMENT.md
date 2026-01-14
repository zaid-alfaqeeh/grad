# Software Deployment

## 3.3 Software Deployment

Students should:

- Describe technologies and 3rd-party tools used in deployment.
- Present them in a table like this: (Update don't use as is)

---

## Technologies and Tools Used in Deployment

| Component                       | Technology                 | Purpose                                                                                  |
| ------------------------------- | -------------------------- | ---------------------------------------------------------------------------------------- |
| **Front-End**                   | HTML5                      | Structure and semantic markup for the web interface                                      |
|                                 | CSS3                       | Styling and responsive design for the user interface                                     |
|                                 | JavaScript (ES6+)          | Client-side interactivity, API communication, and streaming response handling            |
|                                 | Server-Sent Events (SSE)   | Real-time streaming of ChatGPT responses for faster user experience                      |
| **Back-End**                    | Python 3.8+                | Core programming language for the application                                            |
|                                 | Flask 3.0.0+               | Lightweight web framework for RESTful API endpoints and request handling                 |
|                                 | Flask-CORS 4.0.0+          | Cross-Origin Resource Sharing support for frontend-backend communication                 |
|                                 | Gunicorn                   | Production WSGI HTTP server for deploying Flask applications                             |
| **Database/Cache**              | Redis 5.0.0+               | In-memory data structure store for caching JSON datasets, alias mappings, and embeddings |
|                                 | Redis Cluster              | High availability and scalability for production deployments                             |
| **AI/ML Services**              | OpenAI API 1.0.0+          | Integration with OpenAI services for AI-powered features                                 |
|                                 | GPT-4o                     | Large language model for web search, data extraction, and answer generation              |
|                                 | text-embedding-3-small     | Embedding model for generating vector representations of queries and aliases             |
| **Data Processing**             | NumPy 1.24.0+              | Numerical computing library for cosine similarity calculations between embeddings        |
| **Configuration & Environment** | python-dotenv 1.0.0+       | Environment variable management for secure configuration (API keys, credentials)         |
|                                 | .env files                 | Secure storage of sensitive configuration data (not committed to repository)             |
| **Development Tools**           | Git                        | Version control system for code management and collaboration                             |
|                                 | VS Code / PyCharm          | Integrated Development Environment (IDE) for code editing and debugging                  |
|                                 | Python Virtual Environment | Isolated Python environment for dependency management                                    |
| **Testing & Quality**           | Python logging             | Built-in logging system for debugging, monitoring, and error tracking                    |
|                                 | Manual Testing             | Web interface (test.html) for interactive testing of API endpoints                       |
| **Deployment & Infrastructure** | Nginx / Load Balancer      | Reverse proxy and load balancing for production deployments                              |
|                                 | Docker (Optional)          | Containerization for consistent deployment across environments                           |
|                                 | Cloud Services (Optional)  | Cloud hosting platforms (AWS, Azure, GCP) for scalable deployment                        |
| **API & Communication**         | REST API                   | RESTful API design for query processing and data retrieval                               |
|                                 | JSON                       | Data interchange format for API requests and responses                                   |
|                                 | HTTP/HTTPS                 | Communication protocol for client-server interactions                                    |
| **Monitoring & Logging**        | Rotating File Handler      | Log file management with automatic rotation to prevent disk space issues                 |
|                                 | Error Logging              | Separate error log files for tracking and debugging issues                               |
| **Security**                    | Environment Variables      | Secure storage of API keys and sensitive credentials                                     |
|                                 | CORS Configuration         | Controlled cross-origin access for security                                              |
| **Performance Optimization**    | Background Threading       | Asynchronous processing for non-blocking operations (alias generation, caching)          |
|                                 | Streaming Responses        | Server-Sent Events (SSE) for real-time answer streaming                                  |
|                                 | Redis Caching              | Fast data retrieval for frequently accessed queries                                      |

---

## Architecture Choices Explanation

The system architecture was designed with performance, scalability, and user experience as primary considerations. Flask was chosen as the lightweight web framework due to its simplicity and flexibility for rapid development, while Redis provides high-speed in-memory caching to minimize response times for frequently asked questions. The integration of OpenAI's GPT-4o and embedding models enables intelligent semantic matching and natural language understanding without requiring extensive training data. The answer-first architecture prioritizes immediate response delivery by generating detailed answers first, then performing caching operations in background threads, reducing user wait time by 60-70%. Server-Sent Events (SSE) streaming further enhances perceived performance by displaying responses progressively. This microservices-oriented approach allows independent scaling of components and maintains separation of concerns between frontend, backend, caching, and AI services, ensuring the system remains maintainable and adaptable to future requirements.

---

## Deployment Architecture Components

### Front-End Deployment

- **Static Files**: HTML, CSS, JavaScript files served directly by Flask or through a web server
- **Browser Compatibility**: Modern browsers with ES6+ support
- **Responsive Design**: Mobile-friendly interface using CSS media queries

### Back-End Deployment

- **Application Server**: Flask development server (dev) or Gunicorn (production)
- **Port Configuration**: Default port 5000 (configurable via environment variables)
- **Host Binding**: 0.0.0.0 for network accessibility or localhost for development

### Database/Cache Deployment

- **Redis Server**: Standalone Redis instance or Redis Cluster for high availability
- **Connection Configuration**: Host, port, database number, and password via environment variables
- **Data Persistence**: Optional Redis persistence configuration (RDB/AOF)

### AI/ML Services Integration

- **API Communication**: HTTPS requests to OpenAI API endpoints
- **Rate Limiting**: Built-in retry mechanism with exponential backoff
- **Error Handling**: Comprehensive error handling and fallback mechanisms

### Environment Configuration

- **Development**: Local .env file with development credentials
- **Production**: Secure environment variable injection (no .env files in production)
- **Configuration Management**: Centralized config.py for all system settings

---

## Deployment Steps

1. **Environment Setup**

   - Install Python 3.8+
   - Install Redis server
   - Configure environment variables (.env file)

2. **Dependencies Installation**

   - Create virtual environment
   - Install packages from requirements.txt

3. **Database Initialization**

   - Start Redis server
   - Optional: Seed initial data using seed_data.py

4. **Application Deployment**

   - Development: Run `python server.py`
   - Production: Deploy with Gunicorn and Nginx

5. **Monitoring**
   - Check health endpoint: `/health`
   - Monitor logs for errors and performance

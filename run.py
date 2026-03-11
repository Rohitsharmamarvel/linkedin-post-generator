import os

# Fix gRPC fork deadlock on macOS
os.environ['GRPC_POLL_STRATEGY'] = 'poll'
os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'

from app import create_app

env_name = os.environ.get('APP_ENV', 'dev')
app = create_app(env_name)

if __name__ == '__main__':
    # use_reloader=False prevents gRPC/grpcio fork deadlock on macOS Python 3.9
    # debug=True still gives us nice error pages
    app.run(host='0.0.0.0', port=5001, debug=(env_name == 'dev'), use_reloader=False)

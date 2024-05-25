import yaml

def modify_compose(compose_file_path):
    # Load the Docker Compose file
    with open(compose_file_path, 'r') as file:
        compose_data = yaml.safe_load(file)

    # Perform modifications here
    # Example :
    # compose_data['services']['web']['ports'] = ["8000:80"]
    # For example, you can add or update services, adjust configurations, etc.

    # Save the modified Docker Compose file
    modified_compose_path = compose_file_path.replace('.yml', '-modified.yml')
    with open(modified_compose_path, 'w') as file:
        yaml.dump(compose_data, file)

    print(f"Modified Docker Compose file saved to: {modified_compose_path}")

if __name__ == "__main__":
    compose_file_path = "docker-compose.yml"  # Specify the path to your Docker Compose file
    modify_compose(compose_file_path)

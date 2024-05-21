FROM python:3.11

WORKDIR /app

RUN apt update -y && apt install docker-compose -y

COPY requirements.txt ./

RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000

CMD [ "flask", "run", "--host=0.0.0.0", "--port=5000"]
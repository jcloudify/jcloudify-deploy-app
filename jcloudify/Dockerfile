FROM public.ecr.aws/lambda/python:3.9

RUN yum -y install \
    unzip \
    curl \
    && yum clean all

RUN curl -Lo /tmp/sam-installation.zip https://github.com/aws/aws-sam-cli/releases/latest/download/aws-sam-cli-linux-x86_64.zip \
    && unzip /tmp/sam-installation.zip -d /tmp/sam-installation \
    && /tmp/sam-installation/install \
    && rm -rf /tmp/sam-installation /tmp/sam-installation.zip

COPY requirements.txt ./
RUN python3.9 -m pip install -r requirements.txt -t .

COPY app.py ./

CMD ["app.lambda_handler"]

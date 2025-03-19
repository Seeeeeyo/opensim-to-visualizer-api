# Use miniconda as base image
FROM continuumio/miniconda3:latest

# Set working directory
WORKDIR /app

# Create a Python 3.9 environment
RUN conda create -n opensim_env python=3.9 -y
SHELL ["/bin/bash", "-c"]
RUN echo "conda activate opensim_env" >> ~/.bashrc
ENV PATH /opt/conda/envs/opensim_env/bin:$PATH

# Activate the environment for the subsequent RUN commands
RUN conda init bash && \
    . /root/.bashrc && \
    conda activate opensim_env

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install OpenSim
RUN conda install -c opensim-org opensim=4.4 -y

# Copy the application code
COPY . .

# Expose the port
EXPOSE 8000

# Command to run the application
CMD ["conda", "run", "--no-capture-output", "-n", "opensim_env", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"] 
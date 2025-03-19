# Use miniconda with Python 3.9 as base image
FROM continuumio/miniconda3:4.9.2

# Set working directory
WORKDIR /app

# Create a fresh conda environment for OpenSim
RUN conda create -n opensim_env python=3.9 -y && \
    conda clean -afy

# Copy requirements and install Python dependencies
COPY requirements.txt .

# Install OpenSim in the conda environment
RUN conda install -n opensim_env -c opensim-org opensim=4.4 -y && \
    conda clean -afy

# Install Python dependencies in the environment
RUN conda run -n opensim_env pip install -r requirements.txt

# Copy the application code
COPY . .

# Expose the port
EXPOSE 8000

# Command to run the application
CMD ["conda", "run", "-n", "opensim_env", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"] 
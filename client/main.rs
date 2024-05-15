use reqwest::Client;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let url = "http://nginx";

    let client = Client::new();

    let response = client.get(url).send().await?;

    let body = response.text().await?;

    println!("서버로부터 받은 응답: {}", body);
    
    Ok(())
}